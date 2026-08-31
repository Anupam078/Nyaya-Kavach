"""
First synthetic data batch - directly authored (not via external API call),
validated against the LabeledClause schema. Prioritizes the 3 categories
with zero real seed examples (termination_notice_period, dispute_resolution,
renewal_auto_renewal), plus adds diversity (different names/amounts/villages)
to categories that only had 1-2 real examples from the same small document
family.

Honest scope note: this is ~30 examples, not the roadmap's aspirational
"1,000+". Reaching that volume legitimately requires either bulk LLM
generation (see generate_via_ollama.py) or more real field documents -
padding this file with near-duplicates to hit a number would be fake
progress, not real data.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from schemas.clause_schema import LabeledClause

# (clause_id, text, language, doc_type, category, risk, provisions, notes)
RAW_EXAMPLES = [
    # --- termination_notice_period (0 real examples - filling the gap) ---
    ("synth-term-01", "Either party may end this agreement by giving 7 days' notice in writing.",
     "en", "labor_contract", "termination_notice_period", "low", [], "Reasonable, mutual notice period."),
    ("synth-term-02", "कोई भी पक्ष ७ दिन पहले लिखित सूचना देकर यह अनुबंध समाप्त कर सकता है।",
     "hi", "labor_contract", "termination_notice_period", "low", [], "Hindi equivalent."),
    ("synth-term-03", "The lender can end this loan agreement anytime and demand full payment immediately, without notice.",
     "en", "loan_chit", "termination_notice_period", "high", [], "One-sided, no notice at all - favors lender entirely."),
    ("synth-term-04", "जमींदार किसी भी समय बिना किसी सूचना के जमीन वापस ले सकता है।",
     "hi", "land_lease", "termination_notice_period", "high", [], "Landowner can reclaim land anytime with zero notice - leaves cultivator with no security."),

    # --- dispute_resolution (0 real examples - filling the gap) ---
    ("synth-disp-01", "Any dispute about wages will be resolved by the local Gram Panchayat or Labour Officer.",
     "en", "labor_contract", "dispute_resolution", "low", [], "Proper, accessible venue named."),
    ("synth-disp-02", "कोई भी विवाद होने पर साहूकार का फैसला ही अंतिम माना जाएगा।",
     "hi", "loan_chit", "dispute_resolution", "high", ["usurious-loans-1918-s3-reopening"],
     "One-sided - the lender's word is 'final', denying the borrower any real recourse or court access."),
    ("synth-disp-03", "Any disagreement about the crop share will be settled by mutual discussion, or before the village elder if needed.",
     "en", "land_lease", "dispute_resolution", "low", [], "Reasonable informal resolution path, not one-sided."),

    # --- renewal_auto_renewal (0 real examples - filling the gap) ---
    ("synth-renew-01", "This lease will automatically renew each year unless the tenant gives 30 days' written notice to cancel.",
     "en", "land_lease", "renewal_auto_renewal", "medium", [],
     "Auto-renewal itself isn't automatically predatory, but deserves scrutiny - here the 30-day opt-out is fair, so flagged medium not high."),
    ("synth-renew-02", "अगर समय पर पैसा नहीं चुकाया गया, तो कर्ज अपने आप अगले साल के लिए ब्याज सहित बढ़ जाएगा।",
     "hi", "loan_chit", "renewal_auto_renewal", "high", ["usurious-loans-1918-s3-reopening"],
     "Automatic loan rollover with compounding interest - a classic debt-trap mechanism, not a neutral renewal."),
    ("synth-renew-03", "This contract will end after the harvest season and will not renew automatically; a new agreement must be signed for further work.",
     "en", "labor_contract", "renewal_auto_renewal", "low", [], "Explicit, clean, no auto-renewal trap."),

    # --- diversity additions to existing thin categories ---
    ("synth-int-01", "ब्याज हर महीने १०% की दर से बढ़ता रहेगा, चाहे जितना भी समय लगे।",
     "hi", "loan_chit", "interest_finance_terms", "high",
     ["mp-moneylenders-2020-interest-cap-mechanism", "usurious-loans-1918-s3-reopening"],
     "10% per month compounding is almost certainly far above any reasonable notified cap."),
    ("synth-int-02", "Interest will be charged at the rate fixed by the government, reviewed annually.",
     "en", "loan_chit", "interest_finance_terms", "low", ["mp-moneylenders-2020-interest-cap-mechanism"],
     "Compliant, different phrasing than the seed example."),

    ("synth-princ-01", "मैंने राजू सेठ से १५,००० रुपये उधार लिए, जो मुझे ६ महीने में चुकाने हैं।",
     "hi", "loan_chit", "principal_repayment_schedule", "low", [], "Clear amount and term, different names/numbers than seed."),
    ("synth-princ-02", "The full amount plus profit must be repaid within 7 days or the land will be taken.",
     "en", "loan_chit", "principal_repayment_schedule", "high", ["usurious-loans-1918-s3-reopening"],
     "Unreasonably short repayment window plus harsh land-forfeiture consequence."),

    ("synth-pen-01", "If the crop fails, the tenant must still pay the landowner's full share in cash.",
     "en", "land_lease", "penalty_default_consequences", "medium", [],
     "Shifts all crop-failure risk onto the tenant - not illegal outright, but a harsh, one-sided term worth flagging."),
    ("synth-pen-02", "अगर मजदूर बीमार हो जाए तो उसे सूचित करने पर छुट्टी दी जाएगी, कोई जुर्माना नहीं।",
     "hi", "labor_contract", "penalty_default_consequences", "low", [], "Fair sick-leave provision, no penalty."),

    ("synth-dur-01", "The loan is for a fixed term of 6 months from the date of this note.",
     "en", "loan_chit", "duration_term", "low", [], "Clear fixed term."),
    ("synth-dur-02", "यह जमीन हमेशा के लिए खेती हेतु दी जा रही है, कोई निश्चित अवधि नहीं है।",
     "hi", "land_lease", "duration_term", "medium", [],
     "Indefinite/unclear duration is ambiguous and could blur into an unregistered ownership transfer over time."),

    ("synth-wage-01", "Wages will be paid only at the end of the full 6-month contract, not before.",
     "en", "labor_contract", "wage_payment_terms", "high", ["code-on-wages-2019-mp-wage-rate-apr2026"],
     "Withholding all wages for 6 months is a serious risk pattern, close to wage bondage even if the daily rate is fair."),
    ("synth-wage-02", "मजदूरी हर शनिवार को नकद दी जाएगी।",
     "hi", "labor_contract", "wage_payment_terms", "low", [], "Regular, frequent cash payment - healthy pattern."),

    ("synth-hours-01", "काम के घंटे तय नहीं हैं, जब तक मालिक कहे तब तक काम करना होगा।",
     "hi", "labor_contract", "working_hours_conditions", "high", [],
     "No fixed hours at all - open-ended obligation is a strong risk signal, similar gap to the seed set's Rs 200/day example (no working-hours-cap provision yet exists in the legal corpus)."),

    ("synth-own-01", "The cultivator has no ownership rights over the land; it remains fully owned by the landlord.",
     "en", "land_lease", "ownership_transfer", "low", [], "Explicit and unambiguous - no risk."),
    ("synth-own-02", "अगर पैसा नहीं चुकाया गया तो कर्जदार की जमीन साहूकार की हो जाएगी।",
     "hi", "loan_chit", "ownership_transfer", "high", ["mp-land-revenue-1959-s165-6-tribal-land-transfer"],
     "Informal land forfeiture on default, entirely outside any registered legal transfer process - a serious red flag regardless of whether the land is tribal."),

    ("synth-sec-01", "The borrower's motorcycle is kept by the lender as security and will not be returned even after partial repayment.",
     "en", "loan_chit", "security_collateral_pledge", "medium", [],
     "Refusing partial return on partial repayment is a harsh, one-sided term worth flagging even though pledging collateral itself is legal."),
    ("synth-sec-02", "सोने की एक अंगूठी गिरवी रखी गई है, जो पूरा पैसा चुकाने पर वापस कर दी जाएगी।",
     "hi", "loan_chit", "security_collateral_pledge", "low", [], "Fair, clear collateral terms."),

    ("synth-disc-01", "No written record of the share percentage was given to the cultivator; it was only agreed verbally.",
     "en", "land_lease", "mandatory_disclosure_documentation", "high", [],
     "Verbal-only Batai terms are exactly the documentation gap flagged as a priority in the sample-documents manifest's 'next batch' recommendations."),
    ("synth-disc-02", "मजदूर को अनुबंध की एक कॉपी हस्ताक्षर सहित दी गई।",
     "hi", "labor_contract", "mandatory_disclosure_documentation", "low", [], "Worker given a signed copy - good practice."),

    ("synth-other-01", "बटाई अनुबंध", "hi", "land_lease", "other_uncategorized", "not_applicable", [], "Document title."),
    ("synth-other-02", "Witness: Ramu, resident of Rehti village", "en", "labor_contract", "other_uncategorized", "not_applicable", [], "Administrative witness line."),
    ("synth-other-03", "दिनांक: १ अगस्त २०२६", "hi", "loan_chit", "other_uncategorized", "not_applicable", [], "Date line."),
]


def build_synthetic_batch() -> list[LabeledClause]:
    clauses = []
    for clause_id, text, lang, doc_type, category, risk, provisions, notes in RAW_EXAMPLES:
        clauses.append(LabeledClause(
            clause_id=clause_id,
            text=text,
            language=lang,
            doc_type=doc_type,
            clause_category=category,
            risk_label=risk,
            related_provision_ids=provisions,
            source="synthetic_llm_generated",
            notes=notes,
        ))
    return clauses


if __name__ == "__main__":
    batch = build_synthetic_batch()
    print(f"Generated and validated {len(batch)} synthetic examples.\n")

    categories_covered = sorted({c.clause_category.value for c in batch})
    print(f"Categories touched in this batch: {categories_covered}\n")

    out_path = Path(__file__).parent / "synthetic_batch_01.json"
    out_path.write_text(
        json.dumps([c.model_dump() for c in batch], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Written to {out_path}")
