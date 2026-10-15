"""
Nyaya Kavach — Step 7 / Task 3.1: Embed the legal corpus into pgvector.

What this does:
1. Reads every *.json file in legal-corpus/ (the 6 acts from Step 2).
2. Embeds each provision's `simplified_text` using multilingual-e5-base,
   with the "passage: " prefix the model expects for retrieval documents.
3. Upserts each provision into the `legal_provisions` table in Postgres
   (upsert = safe to re-run any time a legal-corpus file changes; it
   won't create duplicates, it'll just update that row).

Run this once after schema.sql, and again any time you edit/add a
legal-corpus JSON file (e.g. when you fill in a NEEDS_MANUAL_VERIFICATION
number).

Setup (one time):
    pip install sentence-transformers psycopg2-binary python-dotenv

Usage:
    python embed_legal_corpus.py
    python embed_legal_corpus.py --corpus-dir ../../legal-corpus
"""

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras
from sentence_transformers import SentenceTransformer

MODEL_NAME = "intfloat/multilingual-e5-base"

# e5 models require a task-specific prefix on the text you embed.
# "passage: " is for documents being stored/searched over.
# "query: "   is for the thing you're searching WITH (used in search_legal_corpus.py).
# Get this wrong and retrieval quality quietly degrades — the model still
# returns *something*, it's just worse, so it's easy to miss if you skip it.
PASSAGE_PREFIX = "passage: "

DEFAULT_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://nyaya:nyaya_dev_password@localhost:5432/nyaya_kavach",
)


def load_provisions(corpus_dir: Path) -> list[dict]:
    """Read every *.json file in legal-corpus/, skip non-provision files like _sources.md."""
    provisions = []
    json_files = sorted(corpus_dir.glob("*.json"))
    if not json_files:
        print(f"No .json files found in {corpus_dir} — check the path.")
        sys.exit(1)

    for f in json_files:
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, list):
            print(f"  Skipping {f.name} — expected a list of provisions, got {type(data)}")
            continue
        for entry in data:
            missing = [k for k in ("provision_id", "act_name", "raw_text", "simplified_text") if k not in entry]
            if missing:
                print(f"  Skipping an entry in {f.name} — missing required field(s): {missing}")
                continue
            provisions.append(entry)
        print(f"  Loaded {len(data)} provisions from {f.name}")

    return provisions


def embed_provisions(provisions: list[dict], model: SentenceTransformer) -> list[dict]:
    texts = [PASSAGE_PREFIX + p["simplified_text"] for p in provisions]
    print(f"\nEmbedding {len(texts)} provisions with {MODEL_NAME} ...")
    embeddings = model.encode(
        texts,
        batch_size=16,
        show_progress_bar=True,
        normalize_embeddings=True,  # so cosine similarity search is well-behaved
    )
    for p, emb in zip(provisions, embeddings):
        p["_embedding"] = emb.tolist()
    return provisions


def upsert_provisions(provisions: list[dict], db_url: str) -> None:
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            for p in provisions:
                cur.execute(
                    """
                    INSERT INTO legal_provisions
                        (provision_id, act_name, section_number, raw_text,
                         simplified_text, jurisdiction, source_url,
                         verification_status, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (provision_id) DO UPDATE SET
                        act_name = EXCLUDED.act_name,
                        section_number = EXCLUDED.section_number,
                        raw_text = EXCLUDED.raw_text,
                        simplified_text = EXCLUDED.simplified_text,
                        jurisdiction = EXCLUDED.jurisdiction,
                        source_url = EXCLUDED.source_url,
                        verification_status = EXCLUDED.verification_status,
                        embedding = EXCLUDED.embedding,
                        updated_at = now();
                    """,
                    (
                        p["provision_id"],
                        p["act_name"],
                        p.get("section_number"),
                        p["raw_text"],
                        p["simplified_text"],
                        p.get("jurisdiction"),
                        p.get("source_url"),
                        p.get("verification_status", "VERIFIED"),
                        p["_embedding"],
                    ),
                )
        conn.commit()
        print(f"\nUpserted {len(provisions)} provisions into legal_provisions.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Embed legal-corpus/*.json into pgvector.")
    parser.add_argument(
        "--corpus-dir",
        type=str,
        default="../../legal-corpus",
        help="Path to the legal-corpus/ folder (default: ../../legal-corpus, i.e. repo root from ml-pipeline/rag/)",
    )
    parser.add_argument("--db-url", type=str, default=DEFAULT_DB_URL)
    args = parser.parse_args()

    corpus_dir = Path(args.corpus_dir).resolve()
    print(f"Reading legal corpus from: {corpus_dir}")
    provisions = load_provisions(corpus_dir)
    print(f"\nTotal provisions loaded: {len(provisions)}")

    flagged = [p for p in provisions if p.get("verification_status") == "NEEDS_MANUAL_VERIFICATION"]
    if flagged:
        print(f"Note: {len(flagged)} provisions are still flagged NEEDS_MANUAL_VERIFICATION — "
              f"they'll still be embedded and retrievable, just carrying that flag through to the DB "
              f"so the risk engine (Step 8) can treat them differently later.")

    model = SentenceTransformer(MODEL_NAME)
    provisions = embed_provisions(provisions, model)

    upsert_provisions(provisions, args.db_url)
    print("\nDone. Run search_legal_corpus.py to test retrieval.")


if __name__ == "__main__":
    main()
