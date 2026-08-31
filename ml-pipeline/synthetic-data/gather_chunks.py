"""
Runs the segmenter across every sample document and attaches doc_type +
language metadata (parsed from the file path/name), producing a flat list
of candidate chunks ready for hand-labeling.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from segmenter.rule_based_segmenter import segment_document

SAMPLES_DIR = Path(__file__).parent.parent.parent / "sample-documents"

DOC_TYPE_FROM_FOLDER = {
    "loan-chit": "loan_chit",
    "land-lease": "land_lease",
    "labor-contract": "labor_contract",
}


def gather_all_chunks() -> list[dict]:
    results = []
    for f in sorted(SAMPLES_DIR.rglob("*.txt")):
        folder = f.parent.name
        doc_type = DOC_TYPE_FROM_FOLDER.get(folder, "other_unsupported")
        language = "hi" if "hindi" in f.stem else "en"
        raw_text = f.read_text(encoding="utf-8")
        chunks = segment_document(raw_text)
        for i, chunk_text in enumerate(chunks, 1):
            results.append({
                "source_file": str(f.relative_to(SAMPLES_DIR)),
                "chunk_index": i,
                "doc_type": doc_type,
                "language": language,
                "text": chunk_text,
            })
    return results


if __name__ == "__main__":
    all_chunks = gather_all_chunks()
    print(f"Total chunks across all documents: {len(all_chunks)}\n")
    out_path = Path(__file__).parent / "all_candidate_chunks.json"
    out_path.write_text(json.dumps(all_chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Written to {out_path}")
