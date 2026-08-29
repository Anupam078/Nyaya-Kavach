# Legal Corpus — Source Log

Every URL and note used to build the legal-corpus JSON files, for audit and future legal review.
Last updated: 29 August 2026.

---

## mp-moneylenders-act-1934.json

- Bare act text (voucher requirement, registration requirement, definitions): https://indiankanoon.org/doc/123708485/
- Bare act text (alternate mirror, registration authority definitions): https://www.legitquest.com/act/madhya-pradesh-moneylenders-act-1934/B809
- MP Moneylenders (Amendment) Act, 2020, Act No. 16 of 2020 — full bare-act text supplied directly by project team member (source PDF at https://prsindia.org/files/bills_acts/acts_states/madhya-pradesh/2020/Act%2016%20of%202020%20Madhya%20Pradesh.pdf is image-scanned and unreadable by automated tools; text was manually transcribed by a human reader)
- RBI Technical Group Report on Money Lending confirming the base 1934 Act (pre-2020) had no fixed interest ceiling: https://rbidocs.rbi.org.in/rdocs/PublicationReport/Pdfs/78893.pdf
- OPEN ITEM: the specific interest rate currently notified by the State Government under Section 2-B has NOT been located. Needs: MP Gazette direct search, RTI request to MP Directorate of Institutional Finance, or a legal database (SCC Online / Manupatra) with full-text notification search.

## usurious-loans-act-1918.json

- Bare act text (Section 3, reopening of transactions; Section 3(2), factors for "excessive" interest): https://indiankanoon.org/doc/1789632/

## mp-land-revenue-code-1959.json

- Section 165 analysis, tribal land transfer restrictions: https://indiankanoon.org/doc/31903436/
- Supreme Court case confirming Section 165(6) scope and 2025 ruling context (State of MP vs Dinesh Kumar, April 2025): https://legalmaestros.com/current-legal-update/justices-sudhanshu-dhulia-and-k-vinod-chandran-uphold-legality-of-tribal-land-sale-a-landmark-ruling-on-section-165-of-the-m-p-land-revenue-code/
- Case law on the lease-vs-transfer distinction in Sec 165(6): https://mphc.gov.in/upload/jabalpur/MPHCJB/2021/WP/3730/WP_3730_2021_FinalOrder_03-Mar-2021.pdf
- OPEN ITEM: precise current scope of the lease/sale distinction is actively litigated — needs law student/advisor sign-off before use in deterministic rules.

## minimum-wages-act-1948-mp.json

- Confirmation Minimum Wages Act 1948 repealed 21 Nov 2025, folded into Code on Wages 2019: https://commoner-law.com/india/workers-rights/minimum-wages
- Universal coverage provision (Section 5) removing "scheduled employment" restriction: https://commoner-law.com/india/workers-rights/minimum-wages
- Madhya Pradesh Code on Wages Rules, 2026 (includes Section 45(2) underpayment claim provision): https://www.lawrbit.com/wp-content/uploads/2026/01/madhya-pradesh-code-on-wages-rules-2026.pdf
- MP wage figures effective 1 April 2026 – 30 September 2026 (semi-skilled ~Rs 13,421/month, skilled ~Rs 15,144/month, VDA Rs 2,850/month general / Rs 2,352/month agricultural): https://futurexsolutions.com/madhya-pradesh-minimum-wages-2026/
- OPEN ITEM: exact unskilled-worker figure for this period not confirmed from a primary source. Zone-specific (A/B/C) rates not confirmed — only state-average figures found. This wage figure itself expires 30 September 2026 and needs refreshing.

## contract-labour-act-1970.json

- Confirmation Contract Labour Act 1970 repealed 21 Nov 2025, folded into OSH Code 2020: https://www.lexology.com/library/detail.aspx?g=b3ba50cd-c9a7-467b-962b-51d8949b636b
- Threshold change from 20 to 50 workers: https://www.pib.gov.in/FactsheetDetails.aspx?id=150475&NoteId=150475&ModuleId=16&reg=3&lang=2
- OSH Code 2020 official citation (Act No. 37 of 2020, effective 21 Nov 2025): https://en.wikipedia.org/wiki/Occupational_Safety,_Health_and_Working_Conditions_Code,_2020
- Critique noting incomplete carry-forward of Inter-State Migrant Workmen Act 1979 protections: https://countercurrents.org/2025/12/occupational-safety-health-and-working-conditions-code-2020-must-be-withdrawn-it-ignores-workers-health/
- OPEN ITEM: OSH Code's specific inter-state migrant worker provisions not yet reviewed in detail — flagged for a closer look given MP's migrant labor context.

## bonded-labour-act-1976.json

- Bare act text (Sections 6, 16, 17): https://www.indiacode.nic.in/bitstream/123456789/1491/1/197619.pdf
- Background and Constitutional basis (Articles 21, 23): https://en.wikipedia.org/wiki/Bonded_Labour_System_(Abolition)_Act,_1976

---

## General notes for whoever reviews this next

- No legal-literate person was on the team as of this corpus's creation. Everything here is best-effort tech-team research from primary and secondary online sources, not legal advice.
- Every entry's `verification_status` field indicates how solid that specific entry is. Anything other than `VERIFIED_FROM_BARE_ACT_TEXT` needs a second look before being used in a deterministic risk-engine rule.
- Two significant corrections were made to this corpus mid-development: (1) the labor law framework was initially cited using repealed Acts before the 2025-26 Labour Code reform was discovered, and (2) the MP Moneylenders interest cap was initially assumed to be a fixed percentage in the Act before the actual delegated-notification mechanism (Section 2-B) was found. Both are now corrected. This history is kept here as a reminder to re-verify assumptions rather than trust them by default.
