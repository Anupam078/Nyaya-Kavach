# Sample Documents — Manifest

**Status: AUTHOR-CONSTRUCTED BOOTSTRAP SAMPLES — NOT REAL FIELD DOCUMENTS.**

These 7 documents (14 files: Hindi + English pairs) were written by the AI assistant to unblock early segmenter/dataset development, because genuine informal rural document formats (handwritten chits, oral Batai arrangements) are not represented in indexed web content — only polished, formal legal-tech templates are, and those would misrepresent the real messiness problem this project exists to solve.

**These must be replaced with real field documents before any final demo or evaluation claim.** Treat them as unit-test fixtures, not training-representative data.

---

## Loan / Moneylending Chit

| File pair | Risk level | Tests / relates to legal-corpus provision |
|---|---|---|
| `loan-chit-01-compliant-*` | Low | Voucher requirement met (`mp-moneylenders-1934-voucher-requirement`), lender registration referenced, interest tied to notified rate (`mp-moneylenders-2020-interest-cap-mechanism`) |
| `loan-chit-02-highrisk-*` | High | No voucher at all, undefined/unbounded interest ("whatever he says"), explicit work-off-debt clause involving a minor (`bonded-labour-1976-core-prohibition`), no lender registration mentioned |

## Land Lease

| File pair | Risk level | Tests / relates to legal-corpus provision |
|---|---|---|
| `land-lease-01-compliant-batai-*` | Low | Standard Batai crop-share terms, explicit non-tribal land status, clear share percentage |
| `land-lease-02-highrisk-tribal-*` | High / needs human review | Tribal (Bhumiswami) landholder, long-term (10yr) lease bundled with a lump-sum payment (blurs lease/sale line), no mention of Collector permission (`mp-land-revenue-1959-s165-6-tribal-land-transfer`) — per that provision's own note, this should be flagged for human review, not auto-classified as a violation, since the lease/sale distinction is legally contested |

## Labor Contract

| File pair | Risk level | Tests / relates to legal-corpus provision |
|---|---|---|
| `labor-contract-01-compliant-*` | Low | Wage (Rs 470/day) matches the current MP notified rate, reasonable hours with a break (`code-on-wages-2019-mp-wage-rate-apr2026`) |
| `labor-contract-02-highrisk-*` | High | Wage (Rs 200/day) well below minimum, advance-payment-for-labor structure with a restriction on leaving (`bonded-labour-1976-core-prohibition`), 14-hour workday, no written agreement |

---

## Clause category coverage check (against the 13-tag taxonomy)

Covered by at least one sample: Interest/finance terms, Principal & repayment, Penalty/default, Duration/term, Wage/payment terms, Working hours, Ownership/transfer, Security/collateral, Mandatory disclosure/documentation, Renewal (implicit in Batai seasonal terms).

**Not yet covered by any sample** — worth adding in the next batch: Termination/notice period, Dispute resolution, Renewal/auto-renewal (explicit case), Other/uncategorized (a genuinely ambiguous clause to test the catch-all).

## Suggested next batch (when you're ready to expand past this bootstrap set)
- A labor contract example that's borderline (not clearly compliant or violating) to test the model's handling of genuine ambiguity
- A loan chit with a partially-filled voucher (some required fields present, some missing) rather than all-or-nothing
- At least one document mixing English and Hindi in the same text (very common in real rural documents, and a real OCR/segmentation challenge)
