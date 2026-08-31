"""
Rule-based clause segmenter (Roadmap Task 1.1).

Chunks raw OCR text into candidate clauses using:
1. Blank-line paragraph breaks (the "\\n\\n whitespace logic" from the roadmap)
2. Regex detection of bullets/numbering and bilingual (Hindi + English)
legal/administrative keywords, to further split multi-line paragraphs at
likely clause boundaries.
3. A sentence-level fallback split (Hindi danda + English periods) for any
remaining chunk that bundles multiple sentences with no line breaks and no
"label: value" structure - added after testing showed real bootstrap
documents (continuous prose, no structure) were otherwise left as one
bloated chunk covering multiple distinct legal concerns.

Output: List[str], per the roadmap's explicit structural requirement.
This function has no knowledge of the LabeledClause schema - it only finds
boundaries. Classification into clause_category happens later, downstream.
"""

import re

# Common English abbreviations that end in a period but do NOT mark a
# sentence boundary. "Rs." appears constantly in these documents - splitting
# on it naively breaks "Rs. 5,000" into two chunks. Extend as new false
# positives surface in real documents.
ABBREVIATIONS = ["Rs", "No", "Mr", "Mrs", "Dr", "St", "Regd", "Ave", "vs", "etc"]

# Legal/administrative keywords that commonly start a clause in these
# documents, even without a paragraph break. Bilingual. Extend this list
# as more real documents surface new recurring terms.
CLAUSE_KEYWORDS = [
    # Hindi
    "ब्याज", "मूलधन", "जुर्माना", "अवधि", "समाप्ति", "मजदूरी", "वेतन",
    "काम के घंटे", "स्वामित्व", "गिरवी", "बटाई", "नवीनीकरण", "विवाद",
    "गवाह", "हस्ताक्षर", "अंगूठा", "पंजीकरण", "लाइसेंस", "चुकाने",
    # English
    "interest", "principal", "penalty", "duration", "term", "termination",
    "wage", "salary", "working hours", "ownership", "collateral", "security",
    "renewal", "dispute", "witness", "signature", "registration", "license",
]

# Bullets, dashes, numbered/lettered list markers (Latin and Devanagari digits)
BULLET_PATTERN = re.compile(
    r'^\s*(?:[•▪●]|[-–*]\s|\d+[.)]|[०-९]+[.)])\s*'
)


def _line_starts_new_clause(line: str) -> bool:
    """
    Heuristic: a line starts a new clause if it's a bullet/numbered item,
    OR if it has a short "label: value" structure where the label contains
    a known clause keyword (e.g. "ब्याज दर: ...", "Wage: Rs. 470 per day").
    Substring match on the label (not strict prefix) because real labels
    are often phrases like "चुकाने की अवधि" where the keyword isn't
    literally the first word.
    """
    stripped = line.strip()
    if not stripped:
        return False
    if BULLET_PATTERN.match(stripped):
        return True

    colon_idx = stripped.find(':')
    if colon_idx == -1 or colon_idx > 30:
        return False
    label = stripped[:colon_idx]
    return any(kw in label for kw in CLAUSE_KEYWORDS)


def _sentence_fallback_split(chunk: str) -> list[str]:
    """
    Splits a chunk at sentence boundaries (Hindi danda '।' or English '.'),
    but only if it contains 2+ sentence terminators - single-sentence chunks
    are left untouched. Protects known abbreviations (e.g. "Rs.") from being
    mistaken for sentence ends.
    """
    terminator_count = chunk.count('।') + len(re.findall(r'\.(?=\s|$)', chunk))
    if terminator_count < 2:
        return [chunk]

    protected = chunk
    for abbr in ABBREVIATIONS:
        protected = re.sub(rf'\b{abbr}\.', f'{abbr}<DOT>', protected)

    parts = re.split(r'(?<=[।.])\s+', protected)
    return [p.replace('<DOT>', '.').strip() for p in parts if p.strip()]


def segment_document(raw_text: str) -> list[str]:
    """
    Chunk raw OCR text into candidate clauses.

    Strategy:
    1. Split on blank-line paragraph breaks.
    2. Within any paragraph that has multiple lines, further split at lines
       that look like the start of a new clause (bullet marker, or a
       keyword-bearing label before a colon).
    3. Apply the sentence-level fallback split to every resulting chunk, to
       catch continuous-prose chunks (no line breaks, no "label:" structure)
       that still bundle multiple distinct sentences.
    4. Drop empty/whitespace-only fragments.

    Remaining known limitation: this is still string-boundary heuristics,
    not true clause understanding. A single sentence that itself covers two
    legal concerns (rare in the samples tested, but possible in real
    documents) will not be split further. That is expected to be handled
    later by the classifier/RAG stages, not the segmenter.
    """
    if not raw_text or not raw_text.strip():
        return []

    paragraphs = re.split(r'\n\s*\n+', raw_text.strip())

    chunks: list[str] = []
    for para in paragraphs:
        lines = [l for l in para.split('\n') if l.strip()]
        if len(lines) <= 1:
            if para.strip():
                chunks.append(para.strip())
            continue

        current: list[str] = []
        for line in lines:
            if _line_starts_new_clause(line) and current:
                chunks.append(' '.join(current).strip())
                current = [line]
            else:
                current.append(line)
        if current:
            chunks.append(' '.join(current).strip())

    chunks = [c.strip() for c in chunks if c.strip()]

    final_chunks: list[str] = []
    for c in chunks:
        final_chunks.extend(_sentence_fallback_split(c))
    return final_chunks


if __name__ == "__main__":
    demo_text = """रसीद

मैं, रामलाल पिता श्यामलाल, निवासी ग्राम खजुरी, यह लिखकर देता हूं कि मैंने सुरेश साहूकार से रुपये १०,००० उधार लिए हैं।
ब्याज दर: राज्य सरकार द्वारा अधिसूचित दर के अनुसार, प्रति वर्ष।
चुकाने की अवधि: १ वर्ष, दिनांक १५ जून २०२७ तक।
गिरवी: कोई संपत्ति गिरवी नहीं रखी गई है।

हस्ताक्षर - रामलाल"""

    result = segment_document(demo_text)
    for i, chunk in enumerate(result, 1):
        print(f"[{i}] {chunk}")
