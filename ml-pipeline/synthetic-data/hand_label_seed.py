"""
Hand-labels a curated selection of real segmenter output chunks (Roadmap
Task 1.2's "manually label ~20 real chunks" step), validated against the
LabeledClause schema. This becomes the seed set for LLM-based synthetic
data generation.

Selection covers, where real examples exist: all 3 doc_types, both
languages, and a deliberate mix of risk levels. Labels are looked up by
(source_file, chunk_index) against the exact text already produced by the
segmenter, to avoid any transcription mismatch between this file and the
actual chunk text.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from schemas.clause_schema import LabeledClause

CHUNKS_PATH = Path(__file__).parent / "all_candidate_chunks.json"

# (source_file, chunk_index) -> (clause_category, risk_label, related_provision_ids, notes)
LABELS = {
    ("loan-chit/loan-chit-01-compliant-english.txt", 4): (
        "interest_finance_terms", "low",
        ["mp-moneylenders-2020-interest-cap-mechanism"],
        "Interest tied to the notified rate, as the law requires.",
    ),
    ("loan-chit/loan-chit-01-compliant-hindi.txt", 4): (
        "interest_finance_terms", "low",
        ["mp-moneylenders-2020-interest-cap-mechanism"],
        "Hindi equivalent of the compliant interest clause.",
    ),
    ("loan-chit/loan-chit-02-highrisk-english.txt", 4): (
        "interest_finance_terms", "high",
        ["mp-moneylenders-2020-interest-cap-mechanism", "usurious-loans-1918-s3-reopening"],
        "Undefined, lender-controlled interest - violates the notified-rate requirement and is a textbook 'harsh and unconscionable' pattern.",
    ),
    ("loan-chit/loan-chit-02-highrisk-hindi.txt", 4): (
        "interest_finance_terms", "high",
        ["mp-moneylenders-2020-interest-cap-mechanism", "usurious-loans-1918-s3-reopening"],
        "Hindi equivalent of the undefined-interest high-risk clause.",
    ),
    ("loan-chit/loan-chit-01-compliant-english.txt", 5): (
        "principal_repayment_schedule", "low", [],
        "Clear, fixed repayment period.",
    ),
    ("loan-chit/loan-chit-02-highrisk-english.txt", 2): (
        "principal_repayment_schedule", "low", [],
        "The amount itself isn't the violation here - the missing voucher (separate chunk) is. Keep this one low to avoid conflating two different risk signals into one label.",
    ),
    ("loan-chit/loan-chit-02-highrisk-english.txt", 3): (
        "penalty_default_consequences", "high",
        ["bonded-labour-1976-core-prohibition"],
        "Work-off-debt clause involving the borrower's son - matches the Bonded Labour Act's core prohibition.",
    ),
    ("loan-chit/loan-chit-02-highrisk-hindi.txt", 3): (
        "penalty_default_consequences", "high",
        ["bonded-labour-1976-core-prohibition"],
        "Hindi equivalent of the bonded-labor penalty clause.",
    ),
    ("labor-contract/labor-contract-02-highrisk-english.txt", 3): (
        "penalty_default_consequences", "high",
        ["bonded-labour-1976-core-prohibition"],
        "Same bonded-labor pattern, but originating in a labor contract rather than a loan chit - useful for teaching the model this pattern isn't tied to one doc_type.",
    ),
    ("labor-contract/labor-contract-02-highrisk-english.txt", 4): (
        "penalty_default_consequences", "high",
        ["bonded-labour-1976-core-prohibition"],
        "Restraint on leaving the job until debt is repaid - a defining feature of bonded labor, not just low pay.",
    ),
    ("land-lease/land-lease-01-compliant-batai-english.txt", 6): (
        "duration_term", "low", [],
        "Standard single-season Batai duration.",
    ),
    ("land-lease/land-lease-01-compliant-batai-hindi.txt", 6): (
        "duration_term", "low", [],
        "Hindi equivalent.",
    ),
    ("labor-contract/labor-contract-01-compliant-english.txt", 3): (
        "duration_term", "low", [],
        "Fixed 3-month work duration, clearly stated.",
    ),
    ("labor-contract/labor-contract-01-compliant-english.txt", 4): (
        "wage_payment_terms", "low",
        ["code-on-wages-2019-mp-wage-rate-apr2026"],
        "Wage matches the current MP notified rate.",
    ),
    ("labor-contract/labor-contract-01-compliant-hindi.txt", 4): (
        "wage_payment_terms", "low",
        ["code-on-wages-2019-mp-wage-rate-apr2026"],
        "Hindi equivalent.",
    ),
    ("labor-contract/labor-contract-02-highrisk-english.txt", 5): (
        "wage_payment_terms", "high",
        ["code-on-wages-2019-mp-wage-rate-apr2026"],
        "Rs 200/day is well below the notified minimum, and it's being deducted from an advance rather than paid outright.",
    ),
    ("labor-contract/labor-contract-02-highrisk-hindi.txt", 5): (
        "wage_payment_terms", "high",
        ["code-on-wages-2019-mp-wage-rate-apr2026"],
        "Hindi equivalent of the underpaid-wage clause.",
    ),
    ("labor-contract/labor-contract-01-compliant-english.txt", 5): (
        "working_hours_conditions", "low", [],
        "Reasonable hours with a break.",
    ),
    ("labor-contract/labor-contract-02-highrisk-english.txt", 6): (
        "working_hours_conditions", "high", [],
        "14-hour workday. NOTE: the legal-corpus does not currently have a provision specifically capping working hours - this is a genuine gap worth adding (likely under the OSH Code 2020) before this category can cite a specific law in the RAG step.",
    ),
    ("land-lease/land-lease-01-compliant-batai-english.txt", 4): (
        "ownership_transfer", "low", [],
        "Ordinary cultivation arrangement, no red flags.",
    ),
    ("land-lease/land-lease-02-highrisk-tribal-english.txt", 2): (
        "ownership_transfer", "high",
        ["mp-land-revenue-1959-s165-6-tribal-land-transfer"],
        "Tribal landholder, long-term (10yr) transfer bundled with a lump sum - the lease/sale distinction is legally contested per the corpus note, so this should route to human review, not an automatic verdict.",
    ),
    ("land-lease/land-lease-02-highrisk-tribal-hindi.txt", 2): (
        "ownership_transfer", "high",
        ["mp-land-revenue-1959-s165-6-tribal-land-transfer"],
        "Hindi equivalent of the tribal land transfer clause.",
    ),
    ("loan-chit/loan-chit-01-compliant-english.txt", 6): (
        "security_collateral_pledge", "low", [],
        "Explicitly no collateral pledged - clean and clear.",
    ),
    ("loan-chit/loan-chit-01-compliant-english.txt", 7): (
        "mandatory_disclosure_documentation", "low",
        ["mp-moneylenders-1934-voucher-requirement"],
        "Voucher requirement satisfied.",
    ),
    ("loan-chit/loan-chit-02-highrisk-english.txt", 5): (
        "mandatory_disclosure_documentation", "high",
        ["mp-moneylenders-1934-voucher-requirement", "mp-moneylenders-1934-registration-required"],
        "No voucher at all - a direct violation, and grounds to doubt the lender is even registered.",
    ),
    ("loan-chit/loan-chit-01-compliant-english.txt", 1): (
        "other_uncategorized", "not_applicable", [],
        "Document title/header, not a substantive clause.",
    ),
    ("loan-chit/loan-chit-01-compliant-english.txt", 9): (
        "other_uncategorized", "not_applicable", [],
        "Signature block, administrative not substantive.",
    ),
}


def build_seed_dataset() -> list[LabeledClause]:
    all_chunks = {
        (c["source_file"], c["chunk_index"]): c
        for c in json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))
    }

    labeled: list[LabeledClause] = []
    for (source_file, idx), (category, risk, provisions, notes) in LABELS.items():
        chunk = all_chunks[(source_file, idx)]
        clause_id = f"{Path(source_file).stem}-c{idx}"
        labeled.append(LabeledClause(
            clause_id=clause_id,
            text=chunk["text"],
            language=chunk["language"],
            doc_type=chunk["doc_type"],
            clause_category=category,
            risk_label=risk,
            related_provision_ids=provisions,
            source="author_constructed_bootstrap",
            notes=notes,
        ))
    return labeled


if __name__ == "__main__":
    seed = build_seed_dataset()
    print(f"Labeled {len(seed)} chunks (target was ~20 per roadmap - {len(seed)} gives good category coverage).\n")

    categories_covered = sorted({c.clause_category.value for c in seed})
    print(f"Clause categories covered ({len(categories_covered)}/13): {categories_covered}\n")

    all_categories = {
        "interest_finance_terms", "principal_repayment_schedule", "penalty_default_consequences",
        "duration_term", "termination_notice_period", "wage_payment_terms", "working_hours_conditions",
        "ownership_transfer", "security_collateral_pledge", "mandatory_disclosure_documentation",
        "dispute_resolution", "renewal_auto_renewal", "other_uncategorized",
    }
    missing = sorted(all_categories - set(categories_covered))
    print(f"NOT covered by any real example ({len(missing)}): {missing}")
    print("These categories will have to rely entirely on the LLM's understanding")
    print("of the category description during synthetic generation - no real seed exists yet.\n")

    out_path = Path(__file__).parent / "seed_labeled_clauses.json"
    out_path.write_text(
        json.dumps([c.model_dump() for c in seed], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Written to {out_path}")
