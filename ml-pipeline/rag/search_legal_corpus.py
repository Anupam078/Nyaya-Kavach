"""
Nyaya Kavach — Step 7 / Task 3.1: Retrieval test + reusable retrieval function.

Two things live here:
1. `retrieve_relevant_law()` — the actual function Step 9 (RAG explanation
   generation) will import and call. Given a flagged clause's text, it
   returns the top-k most relevant legal provisions.
2. An interactive CLI so you can sanity-check retrieval quality right now,
   the same way classify_clause.py let you sanity-check the classifier.

Usage:
    python search_legal_corpus.py
    python search_legal_corpus.py --top-k 5
"""

import argparse
import os

import psycopg2
from sentence_transformers import SentenceTransformer

MODEL_NAME = "intfloat/multilingual-e5-base"
QUERY_PREFIX = "query: "  # the retrieval-side counterpart to PASSAGE_PREFIX in embed_legal_corpus.py

DEFAULT_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://nyaya:nyaya_dev_password@localhost:5432/nyaya_kavach",
)

_model = None  # lazy-loaded, shared across calls so repeated queries don't reload the model


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def retrieve_relevant_law(clause_text: str, top_k: int = 3, db_url: str = DEFAULT_DB_URL) -> list[dict]:
    """
    Given a clause's text, return the top_k most relevant legal provisions
    as a list of dicts: provision_id, act_name, section_number,
    simplified_text, verification_status, similarity.

    This is what Step 9's RAG prompt will call to fill in the
    "Relevant law (retrieved by similarity search)" section of the prompt
    template you designed back in Step 3.
    """
    model = _get_model()
    query_embedding = model.encode(
        QUERY_PREFIX + clause_text,
        normalize_embeddings=True,
    ).tolist()

    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            # <=> is pgvector's cosine distance operator (0 = identical, 2 = opposite).
            # We convert to similarity (1 - distance) so higher = more relevant, which
            # is more intuitive when you're eyeballing results.
            cur.execute(
                """
                SELECT provision_id, act_name, section_number, simplified_text,
                       verification_status, 1 - (embedding <=> %s::vector) AS similarity
                FROM legal_provisions
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
                """,
                (query_embedding, query_embedding, top_k),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "provision_id": r[0],
            "act_name": r[1],
            "section_number": r[2],
            "simplified_text": r[3],
            "verification_status": r[4],
            "similarity": round(r[5], 4),
        }
        for r in rows
    ]


def _interactive(top_k: int, db_url: str):
    print(f"Loading {MODEL_NAME} ... (one-time, first call only)")
    _get_model()
    print("Ready. Type a clause (Hindi or English) to see the top matching law. Ctrl+C to quit.\n")
    while True:
        try:
            clause = input("Clause> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break
        if not clause:
            continue

        results = retrieve_relevant_law(clause, top_k=top_k, db_url=db_url)
        if not results:
            print("  No results — is legal_provisions actually populated? Run embed_legal_corpus.py first.\n")
            continue

        for i, r in enumerate(results, 1):
            flag = "  [UNVERIFIED]" if r["verification_status"] == "NEEDS_MANUAL_VERIFICATION" else ""
            print(f"  {i}. [{r['similarity']:.3f}] {r['act_name']} §{r['section_number']}{flag}")
            print(f"     ({r['provision_id']})")
            print(f"     {r['simplified_text'][:200]}{'...' if len(r['simplified_text']) > 200 else ''}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test retrieval against the embedded legal corpus.")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--db-url", type=str, default=DEFAULT_DB_URL)
    args = parser.parse_args()
    _interactive(args.top_k, args.db_url)
