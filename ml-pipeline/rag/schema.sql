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

-- Approximate nearest-neighbour index for fast cosine similarity search.
-- IVFFlat needs data in the table before it's built well, but creating it
-- empty is fine — it self-tunes as rows are added. `lists = 100` is a
-- reasonable default for a corpus this small (dozens to low hundreds of rows);
-- you would only need to raise this if the corpus grew into the thousands.
CREATE INDEX IF NOT EXISTS legal_provisions_embedding_idx
    ON legal_provisions
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

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
