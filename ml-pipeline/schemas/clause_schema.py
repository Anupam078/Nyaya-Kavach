"""
Shared data contract for a labeled clause, used across the entire ML pipeline:
segmenter output -> synthetic data generation -> model fine-tuning -> risk engine.

This must stay in sync with clause_schema.json (the language-agnostic version,
shared with the Java backend team for their API contract). If you change a field
here, update clause_schema.json to match, and vice versa.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Language(str, Enum):
    HINDI = "hi"
    ENGLISH = "en"


class DocType(str, Enum):
    LOAN_CHIT = "loan_chit"
    LAND_LEASE = "land_lease"
    LABOR_CONTRACT = "labor_contract"
    OTHER_UNSUPPORTED = "other_unsupported"


class ClauseCategory(str, Enum):
    INTEREST_FINANCE_TERMS = "interest_finance_terms"
    PRINCIPAL_REPAYMENT_SCHEDULE = "principal_repayment_schedule"
    PENALTY_DEFAULT_CONSEQUENCES = "penalty_default_consequences"
    DURATION_TERM = "duration_term"
    TERMINATION_NOTICE_PERIOD = "termination_notice_period"
    WAGE_PAYMENT_TERMS = "wage_payment_terms"
    WORKING_HOURS_CONDITIONS = "working_hours_conditions"
    OWNERSHIP_TRANSFER = "ownership_transfer"
    SECURITY_COLLATERAL_PLEDGE = "security_collateral_pledge"
    MANDATORY_DISCLOSURE_DOCUMENTATION = "mandatory_disclosure_documentation"
    DISPUTE_RESOLUTION = "dispute_resolution"
    RENEWAL_AUTO_RENEWAL = "renewal_auto_renewal"
    OTHER_UNCATEGORIZED = "other_uncategorized"


class RiskLabel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    NOT_APPLICABLE = "not_applicable"


class ClauseSource(str, Enum):
    AUTHOR_CONSTRUCTED_BOOTSTRAP = "author_constructed_bootstrap"
    SYNTHETIC_LLM_GENERATED = "synthetic_llm_generated"
    REAL_FIELD_DOCUMENT = "real_field_document"


class LabeledClause(BaseModel):
    """A single labeled clause chunk - the shared unit flowing through the pipeline."""

    model_config = {"extra": "forbid"}

    clause_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier, e.g. 'loan-chit-02-highrisk-hindi-c1'.",
    )
    text: str = Field(..., min_length=1, description="Clause text in its original language.")
    language: Language
    doc_type: DocType
    clause_category: ClauseCategory = Field(
        ..., description="Exactly one tag. Single-label by design - do not make this a list."
    )
    risk_label: RiskLabel
    related_provision_ids: list[str] = Field(
        default_factory=list,
        description="Optional provision_id links into the legal-corpus JSON files.",
    )
    source: ClauseSource
    notes: Optional[str] = None

    @field_validator("text")
    @classmethod
    def text_not_just_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be empty or whitespace-only")
        return v


if __name__ == "__main__":
    # Quick self-check: validate a couple of real examples pulled from the
    # bootstrap sample documents, to prove the schema actually fits real data
    # before Step 4 code starts depending on it.

    example_1 = LabeledClause(
        clause_id="loan-chit-02-highrisk-english-c1",
        text=(
            "If I cannot pay the money back, my son will work on Natthu Seth's "
            "farm until the full amount is paid off."
        ),
        language=Language.ENGLISH,
        doc_type=DocType.LOAN_CHIT,
        clause_category=ClauseCategory.PENALTY_DEFAULT_CONSEQUENCES,
        risk_label=RiskLabel.HIGH,
        related_provision_ids=["bonded-labour-1976-core-prohibition"],
        source=ClauseSource.AUTHOR_CONSTRUCTED_BOOTSTRAP,
        notes="Work-off-debt clause involving a minor - matches Bonded Labour Act pattern.",
    )

    example_2 = LabeledClause(
        clause_id="labor-contract-01-compliant-english-c1",
        text="Wage: Rs. 470 per day, paid weekly.",
        language=Language.ENGLISH,
        doc_type=DocType.LABOR_CONTRACT,
        clause_category=ClauseCategory.WAGE_PAYMENT_TERMS,
        risk_label=RiskLabel.LOW,
        related_provision_ids=["code-on-wages-2019-mp-wage-rate-apr2026"],
        source=ClauseSource.AUTHOR_CONSTRUCTED_BOOTSTRAP,
        notes="Wage matches the current MP notified rate.",
    )

    example_3 = LabeledClause(
        clause_id="land-lease-01-compliant-batai-english-c1",
        text="Share terms: Half the crop (50%) to the landowner, half (50%) to the cultivator.",
        language=Language.ENGLISH,
        doc_type=DocType.LAND_LEASE,
        clause_category=ClauseCategory.OWNERSHIP_TRANSFER,
        risk_label=RiskLabel.NOT_APPLICABLE,
        source=ClauseSource.AUTHOR_CONSTRUCTED_BOOTSTRAP,
        notes="Standard Batai split, nothing concerning.",
    )

    for ex in (example_1, example_2, example_3):
        print(ex.model_dump_json(indent=2))
        print("---")

    print("All 3 example clauses validated successfully against the schema.")
