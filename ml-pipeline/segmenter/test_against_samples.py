import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from segmenter.rule_based_segmenter import segment_document

SAMPLES_DIR = Path(__file__).parent.parent.parent / "sample-documents"

def main():
    txt_files = sorted(SAMPLES_DIR.rglob("*.txt"))
    print(f"Found {len(txt_files)} sample documents.\n")

    for f in txt_files:
        raw_text = f.read_text(encoding="utf-8")
        chunks = segment_document(raw_text)
        print(f"=== {f.relative_to(SAMPLES_DIR)} ===")
        print(f"  {len(chunks)} chunks produced")
        for i, c in enumerate(chunks, 1):
            preview = c if len(c) <= 80 else c[:77] + "..."
            print(f"  [{i}] {preview}")
        print()

if __name__ == "__main__":
    main()
