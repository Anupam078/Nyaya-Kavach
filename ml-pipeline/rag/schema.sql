-- Nyaya Kavach — Legal Corpus Vector Table (Step 7 / Task 3.1)
-- Run this once against the nyaya_kavach database.

-- Enables pgvector's `vector` type and similarity operators (<=>, <->, <#>)
CREATE EXTENSION IF NOT EXISTS vector;

-- One row per statutory provision/section from legal-corpus/*.json.
-- Mirrors the JSON shape you already saved in Step 2 — no reshaping needed.
CREATE TABLE IF NOT EXISTS legal_provisions (
    id                  SERIAL PRIMARY KEY,
    provision_id        TEXT UNIQUE NOT NULL,   -- e.g. 'mp-moneylenders-1934-s4'
    act_name            TEXT NOT NULL,
    section_number      TEXT,
    raw_text            TEXT NOT NULL,
    simplified_text     TEXT NOT NULL,          -- what actually gets embedded + shown to users
    jurisdiction        TEXT,
    source_url          TEXT,
    verification_status TEXT DEFAULT 'VERIFIED', -- carries over your NEEDS_MANUAL_VERIFICATION flags
    embedding            vector(768),            -- multilingual-e5-base output dimension
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);

-- NO vector index on purpose (for now).
-- The previous version built an IVFFlat index (lists = 100) on an EMPTY table,
-- with a comment saying it "self-tunes as rows are added". It does not:
-- IVFFlat computes its cluster centres once, at build time. Built on an empty
-- table, those centres are meaningless, and with ~12-100 rows spread across 100
-- lists a query (which probes 1 list by default) returned 0 rows for ~87% of
-- test queries and never returned the 3 requested. pgvector itself warns about
-- this: "ivfflat index created with little data. This will cause low recall."
-- For a corpus this small, exact search (sequential scan) is instant and always
-- correct. Revisit only if the corpus grows into the thousands - and then build
-- the index AFTER loading data (or use HNSW, which does not need training data).
DROP INDEX IF EXISTS legal_provisions_embedding_idx;

-- Three corpus entries (wage rates, OSH Code) have no verbatim statute text
-- because their source was a secondary summary, not a bare act. Storing a
-- fake raw_text would misrepresent that, so raw_text is allowed to be NULL.
-- Downstream code should always use simplified_text.
ALTER TABLE legal_provisions ALTER COLUMN raw_text DROP NOT NULL;

-- Keep updated_at honest on re-embeds.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_legal_provisions_updated_at ON legal_provisions;
CREATE TRIGGER trg_legal_provisions_updated_at
    BEFORE UPDATE ON legal_provisions
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();
