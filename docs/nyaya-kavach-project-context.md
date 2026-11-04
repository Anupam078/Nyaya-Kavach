# Nyaya Kavach — Complete Project Context Document

**Document purpose:** This is the single source of truth for brainstorming, scoping, and design before any code is written. It defines every feature, why it exists, how it should be built, how it interacts with everything else, and what's still open. Treat this as a living document — update it as decisions are made.

**Prepared as:** Senior Software Architect + Product Manager working document
**Project:** Nyaya Kavach — a two-phase legal protection platform (Prevention + Legal Aid)
**Team size:** 6 members | **Timeline:** 2 semesters

---

## 1. Product Vision & Core Thesis

### 1.1 The problem, stated precisely
Rural and semi-literate populations in India face legal harm at two distinct moments:

1. **Before harm occurs** — they sign documents (land leases, moneylending chits, labor contracts, contract-farming agreements) they don't fully understand, because there is no accessible way to verify fairness at the point of decision.
2. **After harm has occurred** — once trapped in a dispute, they face a legal aid system that is structurally too thin to reach them (1 clinic per ~163 villages, ~15% rural access to legal aid) and a court system with ~47 million pending cases where relief is slow.

**The core insight:** these are not two separate problems — they are two ends of the same lifecycle, and no existing product treats them as one continuous flow. Legal-tech tools review contracts for people who already have lawyers. Legal aid engages only after a dispute exists. Nobody intervenes *at the signature* — the actual moment where most harm is created.

### 1.2 Product thesis
Nyaya Kavach is **one system, two phases, one data pipeline**:
- **Phase 1 (Kavach — Prevention):** Stop harm before it happens by analyzing a document before signing.
- **Phase 2 (Nyaya Setu — Legal Aid):** If harm already happened (or Phase 1 flags something too late), hand the person to an agentic paralegal pipeline that gets them real legal help, with a human lawyer always in the loop.

The output of Phase 1 (a risk report) becomes the input of Phase 2 (case intake). This continuity is the single most important architectural and narrative decision in the entire product.

### 1.3 Non-goals (explicitly out of scope)
- This is **not** a replacement for lawyers — every actionable legal output requires human sign-off.
- This is **not** a general-purpose contract-review tool for businesses (scope is informal/rural-facing documents: leases, chits, labor agreements, farming contracts).
- This is **not** a law-enforcement or compliance surveillance tool.
- This does **not** make final legal determinations or predict court outcomes — it explains risk and routes to humans.

---

## 2. Users & Personas

| Persona | Description | Primary need |
|---|---|---|
| **Rural/migrant worker or farmer** (primary end user) | Low-to-medium literacy, regional language speaker, basic Android phone, limited/no legal knowledge | "Is this safe to sign?" / "I'm already stuck — help me." |
| **Village volunteer / community health worker (ASHA-like)** | Digitally literate, trusted intermediary, may operate the app on behalf of end users | Needs a simple assisted-mode UI to help multiple villagers |
| **Panel lawyer / paralegal volunteer** | Verified legal professional attached to a legal aid clinic or NGO | Needs a dashboard to review AI-drafted case work quickly and approve/reject |
| **Legal aid clinic administrator / NGO coordinator** | Manages a roster of lawyers and case load | Needs visibility into incoming cases, urgency triage, assignment |
| **District legal services authority (future/stretch)** | Government-side stakeholder | Aggregate visibility into systemic patterns (e.g., a spike in a specific type of exploitative contract in one district) |

**Key design implication:** the primary end user is very likely *not* the one interacting with a screen fluently. Every feature must have a voice-first or assisted-mode path, not just a text/app UI.

---

## 3. System Overview — High-Level Architecture

```
                        ┌─────────────────────────────┐
                        │        Client Layer          │
                        │  (App / WhatsApp Bot / IVR)  │
                        └───────────────┬───────────────┘
                                        │
                        ┌───────────────▼───────────────┐
                        │        API Gateway             │
                        │  (Auth, rate limiting, routing)│
                        └───────────────┬───────────────┘
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        │                               │                                │
┌───────▼────────┐          ┌──────────▼──────────┐          ┌─────────▼─────────┐
│  Phase 1:        │          │   Shared Core        │          │  Phase 2:          │
│  Kavach Service  │◄────────►│   Services           │◄────────►│  Nyaya Setu        │
│  (Prevention)    │          │  - OCR Pipeline       │          │  (Agentic Legal    │
│                  │          │  - Legal RAG Core     │          │   Aid Network)     │
│                  │          │  - Voice STT/TTS      │          │                    │
│                  │          │  - Case/Doc DB        │          │                    │
└──────────────────┘          └───────────────────────┘          └────────────────────┘
                                        │
                        ┌───────────────▼───────────────┐
                        │   Escalation & Human-in-Loop   │
                        │  (Lawyer dashboard, clinic net) │
                        └─────────────────────────────────┘
```

**Architectural style:** Modular monolith to start (simpler for a 6-person team to build/debug across 2 semesters), with clear service boundaries so it *can* be split into microservices later (OCR service, RAG service, agent-orchestration service are natural seams). Avoid premature microservices — the team's velocity matters more than distributed-systems purity at this scale.

---

## 4. Shared Core Services (Built Once, Used by Both Phases)

These exist because Phase 1 and Phase 2 both need document understanding, legal knowledge, and multilingual voice. Building them once avoids duplicated engineering and is the technical justification for treating this as one product.

### 4.1 OCR & Document Ingestion Pipeline

**Why it exists:** Both phases start with a physical or photographed document that needs to become structured text.

**User problem solved:** Villagers have paper documents, often handwritten or poorly printed, in regional scripts. Generic OCR fails on this.

**Implementation:**
- **Frontend:** Camera capture component with real-time framing guidance (edge detection overlay so user aligns the document correctly), retake/confirm flow, multi-page capture for longer contracts.
- **Preprocessing:** OpenCV pipeline — deskew, denoise, contrast/brightness normalization, auto-crop to document boundary. This runs client-side where possible (faster feedback) and server-side as a fallback/verification.
- **OCR engine:** Start with a managed OCR API (Google Cloud Vision or similar) for regional-script + handwriting support, since training a competitive OCR model from scratch is out of scope for 2 semesters. Tesseract can be evaluated as a self-hosted fallback for cost/offline scenarios, but expect lower accuracy on handwriting.
- **Confidence handling:** Per-line/per-word confidence scores. Low-confidence spans are highlighted back to the user for manual confirmation or re-capture of just that region — this avoids a "garbage in, garbage out" failure silently propagating into legal risk analysis.
- **Output format:** Structured JSON — `{ page, line, text, bbox, confidence, script_detected }` — stored alongside the original image (image retained for audit/human review).

**APIs:**
- `POST /documents/upload` — accepts image(s), returns `document_id`, kicks off async OCR job
- `GET /documents/{id}/ocr-status` — polling endpoint (or WebSocket push) for OCR completion
- `GET /documents/{id}/text` — structured OCR output

**Database:** `documents` table (id, user_id, upload_timestamp, image_urls[], ocr_status), `document_text_blocks` table (document_id, page, line_no, text, confidence, bbox_coords)

**Security/privacy:** Documents often contain sensitive personal/financial data (Aadhaar numbers, bank details, land records). Images and extracted text must be encrypted at rest (AES-256), access-controlled per user, and never used to train third-party models without explicit consent flow. Retention policy needs definition (see §9.2).

**Interacts with:** Feeds directly into Document Structuring (§4.3 under Phase 1) and Case Intake document upload (Phase 2, §6.1).

### 4.2 Legal Knowledge Core (RAG Pipeline)

**Why it exists:** Both the risk classifier's explanations (Phase 1) and the paralegal research agent (Phase 2) need to ground their outputs in actual law, not model hallucination.

**User problem solved:** Prevents the AI from inventing legal claims — every risk flag or legal suggestion must trace back to a real statute/provision.

**Implementation:**
- **Corpus:** Curated, simplified text of relevant Indian statutes — Model Tenancy Act, state-specific tenancy laws, Moneylenders Acts / RBI interest rate caps, Minimum Wages Act, Contract Labour Act, Consumer Protection Act, RTI Act, relevant BNS (Bharatiya Nyaya Sanhita) sections for common disputes. This corpus needs to be built/curated by the team — a genuinely significant content-engineering task, not just a coding task. Budget real time for this (legal research, ideally with an advisor or law-student collaborator).
- **Chunking strategy:** Chunk by provision/section, not arbitrary token windows, so retrieval returns coherent legal units.
- **Embeddings + Vector DB:** Use an embedding model (e.g., a multilingual sentence embedding model, since queries may come in regional language) and store in pgvector (simplest — keeps it inside your existing Postgres, avoids managing a separate vector DB service) or a managed option like Pinecone/Weaviate if scale demands it later.
- **Retrieval:** Given a clause or a case-fact summary, retrieve top-k relevant provisions with citation metadata (act name, section number).
- **Generation:** An LLM (via API) takes the retrieved provisions + the specific clause/case context and generates a plain-language explanation, explicitly prompted to only state what's grounded in retrieved text and to flag uncertainty rather than invent specifics.

**APIs:**
- `POST /legal-rag/query` — internal service endpoint, takes `{ query_text, context_type: "clause"|"case", top_k }`, returns `{ provisions: [...], generated_explanation }`

**Database:** Vector table (provision_id, embedding, act_name, section_number, raw_text, simplified_text, jurisdiction)

**Design trade-off to flag:** Indian law varies by state (especially tenancy and moneylending law). Decide early: do you scope to 1–2 states for the MVP (recommended — e.g., focus on your pilot region) or attempt a generalized multi-state corpus? Scoping to one state for Semester 1 is strongly advised — this is a scope-control decision your supervisor will respect.

**Interacts with:** Risk Classification Engine (Phase 1), Research Agent (Phase 2).

### 4.3 Multilingual Voice Layer (STT/TTS)

**Why it exists:** The primary persona often can't or prefers not to read. Every explanation, alert, or conversational intake needs a voice path.

**Implementation:**
- **STT:** For conversational intake (Phase 2) and voice-logging use cases — use a managed multilingual ASR API (or India-specific options like Bhashini, which is worth exploring given it's a government-backed multilingual AI initiative — citing this in your pitch is a strong alignment point).
- **TTS:** For reading out risk explanations and legal information in regional language — same rationale, Bhashini or a commercial multilingual TTS API.
- **Fallback:** For areas with poor connectivity, consider whether a lightweight on-device TTS (for a small set of pre-generated common phrases) is worth building — likely a Semester 2 stretch, not a Semester 1 requirement.

**Interacts with:** Risk explanation delivery (Phase 1), conversational intake (Phase 2), alerts/reminders (Phase 2 tracking).

### 4.4 Case & Document Management Database

**Why it exists:** Single source of truth for a person's documents, risk reports, and legal cases over time — since the same person may interact with the system multiple times across months/years.

**Implementation:** PostgreSQL as the primary relational store. Core entities:
- `users` (id, phone_number, name, preferred_language, village/district, created_at)
- `documents` (as above)
- `risk_reports` (document_id, overall_risk_level, generated_at, clauses[] with risk scores)
- `cases` (id, user_id, category, urgency_tier, status, created_at, linked_risk_report_id nullable)
- `case_events` (case_id, event_type, timestamp, actor) — audit trail
- `lawyers` / `clinics` (verification status, specialization, workload)

**Security:** Row-level access control (a user can only see their own data; a lawyer can only see cases assigned to them; admin roles scoped by clinic/district). This is a genuine implementation requirement, not an afterthought — legal case data is highly sensitive.

---

## 5. Phase 1 — Kavach (Prevention Layer) — Detailed Feature Breakdown

### 5.1 Document Capture & Type Detection

**User problem:** The system needs to know what *kind* of document it's looking at before it can assess risk, since risk criteria differ completely between a land lease and a labor contract.

**Implementation:** A lightweight text classifier (can start as a fine-tuned small transformer, or even a strong prompt-based LLM classifier for MVP) runs on the OCR'd text to categorize: land lease / loan-moneylending chit / labor contract / contract-farming agreement / other-unsupported. If "other-unsupported," the system should say so honestly rather than force-fit a wrong rule-set — an important trust-preserving design decision.

**Edge case:** Multi-purpose or hybrid documents (e.g., a labor contract with an embedded loan-advance clause). Design the classifier to support multi-label output, not just single-category, from the start — retrofitting this later is painful.

### 5.2 Clause Segmentation & Categorization

**User problem:** Legal risk lives in specific clauses, not the whole document — the system needs to isolate and categorize each clause to reason about it individually.

**Implementation:** After type detection, a clause-segmentation step (rule-based sentence/paragraph splitting + a classifier to tag each segment: interest terms, termination conditions, penalty clauses, ownership/transfer clauses, payment terms, duration, dispute-resolution clause, wage/hours terms, etc.)

**Technical challenge to flag honestly:** Real village-level documents are often poorly structured — no numbered clauses, run-on sentences, inconsistent formatting. Your segmentation model needs training data reflecting this messiness, not clean legal-template text. This is likely your single hardest NLP problem in Phase 1 — budget significant time for it.

### 5.3 Risk Classification Engine (Core AI Feature)

**Why it exists:** This is the product's central value — turning raw clauses into an actionable risk verdict.

**Implementation — dual-layer approach (important design decision):**
1. **Deterministic rules layer:** Encodes known legal thresholds (e.g., "moneylender interest rate exceeds the state-mandated cap," "termination clause violates minimum notice period under Model Tenancy Act," "wage terms below applicable minimum wage"). This layer is explainable, auditable, and doesn't hallucinate — use it wherever a hard legal number/threshold exists.
2. **ML/LLM classifier layer:** For softer risk patterns that aren't a clean numeric threshold (e.g., unusually one-sided dispute-resolution clauses, ambiguous ownership language, missing standard protections). Trained on a custom-annotated dataset your team builds (real anonymized examples + synthetically generated risky/fair clause pairs).

**Why both layers matter:** Rules alone miss nuanced exploitative patterns; ML alone risks being a black box that's hard to defend if challenged (e.g., "why did the AI say this was risky?"). The combination gives you defensible, explainable output — a strong point to make to your supervisor about engineering maturity.

**Output:** Per-clause risk score (Low/Medium/High) + overall document risk level + the specific reason (rule violated OR pattern matched) for each flag.

**APIs:** `POST /kavach/analyze` — takes `document_id`, returns `risk_report_id` (async, since OCR + classification + RAG explanation generation takes real processing time — design for a "processing... we'll notify you" UX, not a spinner the user stares at).

### 5.4 RAG-Grounded Explanation Generation

Already covered in §4.2 — the Risk Classification output is fed to the Legal RAG Core, which retrieves relevant provisions and generates a plain-language explanation for each flagged clause.

**Important business-logic decision:** Explanations must always cite *which* rule or provision triggered the flag. Never present a bare "this seems risky" — always "this clause allows X, which conflicts with [Act/Section], because [Y]." This is both a trust feature and a legal-safety feature (it keeps the system in "informational" territory rather than "legal advice" territory — see §9.1 on liability).

### 5.5 Multilingual Delivery & Verdict

**Implementation:** Combines TTS (§4.3) with a simplified visual UI: the document image shown with flagged clauses highlighted in color (red/yellow/green), tap-to-hear explanation per clause, and an overall verdict banner ("Safe to sign" / "Risky — listen to why" / "High risk — do not sign without help").

### 5.6 Decision Fork & Handoff to Phase 2

**Why it exists:** This is the architectural hinge of the entire product.

**Implementation:** If overall risk is Medium/High, present two clear options:
- "Get simplified renegotiation points" (a lightweight LLM-generated suggestion of what to ask the other party to change — grounded in the same RAG output)
- "Talk to someone about this" → this creates a **draft case** in Phase 2's intake system, pre-filled with the risk report, document, and category — so the user doesn't have to re-explain everything from scratch.

**This pre-fill mechanic is the single feature that justifies calling this "one product" rather than two — make sure it's built early and correctly, not bolted on later.**

### 5.7 Document Locker (Personal Record)

**Why it exists:** Even a "safe to sign" document should be saved — if a dispute arises years later, having a stored, timestamped copy with the original risk assessment is valuable evidence.

**Implementation:** Simple encrypted storage of all analyzed documents under the user's account, retrievable later, timestamped. This becomes evidence input for Phase 2 cases far in the future — a nice long-term value loop worth mentioning to your supervisor (the product gets more useful to a user over time, not just at first use).

---

## 6. Phase 2 — Nyaya Setu (Agentic Legal Aid Network) — Detailed Feature Breakdown

### 6.1 Intake Agent

**User problem:** Villagers don't know how to frame their legal problem in a way that maps to a legal category — they just know "something bad is happening to me."

**Implementation:** A conversational agent (LLM-driven, voice or text, regional language) that asks structured but natural questions: what happened, when, who's involved, what documents exist, what outcome they want. Uses slot-filling internally (a structured schema being populated conversationally) rather than a rigid form.

**Handoff case:** If arriving from Phase 1, the risk report and document are pre-attached; the agent's first message acknowledges this ("I see you were told this loan agreement had a risky interest clause — tell me what's happened since you signed it") rather than starting from zero.

**Edge case handling:** Ambiguous or multi-issue narratives (a person describing both a land dispute AND a domestic issue) — the agent should be able to split this into multiple case threads rather than forcing one category.

### 6.2 Classifier/Router Agent

**Implementation:** Takes the structured intake object, classifies into case category (RTI / consumer / labor / land / domestic / criminal / other) and urgency tier. Urgency logic should be rule-based and conservative (better to over-flag urgency than under-flag) — triggers include mentions of eviction deadlines, threats, immediate court dates, or violence.

**Important safety design:** If domestic violence, self-harm, or immediate physical danger is detected in the intake conversation, this must **immediately** route to a human/crisis-appropriate flow, bypassing the standard AI pipeline entirely — this is a hard product requirement, not optional polish.

### 6.3 Research Agent

Uses the shared Legal RAG Core (§4.2) to pull relevant statutes/provisions matched to the specific case facts, producing a structured "legal basis" object with citations.

### 6.4 Drafting Agent

**Implementation:** LLM constrained to only use the retrieved legal basis, generates: (a) a plain-language rights/options explanation for the user, (b) a draft document appropriate to the case type (RTI application, consumer complaint, legal aid application, Panchayat petition template).

**Hard constraint:** Every draft is watermarked/labeled "AI-generated draft — pending lawyer review," both in the UI and embedded in the document metadata, so it can never be mistaken for a finalized legal document if it leaks outside the review flow.

### 6.5 Human-in-the-Loop Verification (Lawyer Dashboard)

**Why it exists:** This is your core ethical and legal-safety gate — the system must never let unverified AI legal output reach a court or authority.

**Implementation:** A dashboard for panel lawyers/paralegal volunteers showing queued cases (sorted by urgency), case summary, AI-generated draft, one-click approve/edit/reject, and a comment/feedback field. Approved drafts get finalized and released to the user; rejected/edited ones loop back with lawyer notes (potentially re-invoking the Drafting Agent with corrections, or handled manually).

**Workload consideration:** With a limited number of panel lawyers per clinic, you need a triage/assignment algorithm (round-robin, load-balanced by case category expertise, or urgency-weighted) — a small but real scheduling problem worth designing properly rather than defaulting to "first available."

### 6.6 Escalation Agent

**Implementation:** Runs independently of the drafting pipeline for high-urgency cases — sends an immediate structured alert (SMS/notification) to the nearest legal aid clinic/NGO partner with a case summary, so a human is aware even while AI drafting is still in progress. This decouples "get a human aware fast" from "produce a polished document," which matters because polished documents take longer to generate correctly.

### 6.7 Tracking Agent

**Implementation:** Maintains case status state machine (submitted → under review → filed → hearing scheduled → resolved/closed), sends automated voice/SMS reminders for required actions or upcoming dates, and closes the feedback loop by recording case outcomes — which should periodically feed back into improving the Classifier and Research agents (a genuine "the system gets smarter over time" story, though full retraining pipelines are a stretch goal, not Semester 1 scope).

### 6.8 Escalation Network / Clinic Directory

**Why it exists:** None of the above works without a real, verified directory of legal aid clinics, NGOs, and panel lawyers to escalate to.

**Implementation consideration — this is a genuine non-technical dependency:** Your team needs at least one real partner organization (a legal aid NGO, a law school legal clinic, District Legal Services Authority contact) for the pilot, or this entire phase has nowhere to actually escalate to. **Flag this to your supervisor early** — it's a project dependency outside pure engineering, and identifying/onboarding a partner organization should be a tracked milestone starting Semester 1, not left until Semester 2.

---

## 7. Complete Application Flow — User Journeys

### 7.1 Journey A: First-time user, document is safe
1. User downloads app / opens WhatsApp bot → onboarding (name, phone, language preference, village/district — minimal friction, no complex signup)
2. Taps "Check a document" → camera opens with framing guide
3. Captures document (possibly multiple pages) → sees "Analyzing..." status
4. OCR completes → type detection identifies "loan agreement"
5. Clause segmentation + risk classification runs (async, ~seconds to low minutes depending on document length)
6. Result: "This looks safe" verdict, in voice + text, with a summary of key terms (interest rate, duration, repayment schedule) read aloud for confirmation
7. Document saved to locker automatically
8. Session ends — no further action needed

### 7.2 Journey B: First-time user, document is risky, chooses to get help
1–5. Same as above, but result is "High risk" verdict
6. Voice explanation: "This clause lets the lender take your land if you're even one day late on payment — this is unusual and not standard practice"
7. User taps "Talk to someone about this"
8. System creates a draft Phase 2 case, pre-filled with document + risk report + category (loan/moneylending)
9. Intake Agent starts conversation: "I see this loan agreement has a risky clause — has the lender asked you to sign yet, or already signed?"
10. If not yet signed: conversation focuses on renegotiation guidance + connecting to a local volunteer for in-person support if desired
11. If already signed and a dispute exists: full intake proceeds (§6.1) → classification → research → drafting → lawyer review → user receives finalized guidance/document

### 7.3 Journey C: Returning user with an existing unrelated dispute (no Phase 1 trigger)
1. User opens app → "I have a problem" (direct entry to Phase 2, no document scan involved)
2. Intake Agent conversation proceeds normally (§6.1)
3. Classification → Research → Drafting → Lawyer review → Escalation if urgent → Tracking begins

### 7.4 Journey D: Assisted mode (via village volunteer)
1. Volunteer opens app in "Assisted Mode" → selects/creates the villager's profile
2. Same flows as above, but UI includes volunteer-facing helper text and the ability to manage multiple pending cases across different villagers
3. Notifications (SMS/voice) can go to both the villager's phone and the volunteer's, since the villager's phone may not always be with them or may be shared within a household

### 7.5 Journey E: Lawyer/paralegal review flow
1. Lawyer logs into dashboard → sees urgency-sorted case queue
2. Opens a case → sees intake summary, AI research (with citations), AI draft
3. Edits draft inline or approves as-is, or requests more info (triggers a follow-up conversation with the user via Intake Agent)
4. Approves → finalized document released to user + case status updated → Tracking Agent takes over

---

## 8. Data Flow Summary

```
Document Photo → OCR → Structured Text → Type Classification → Clause Segmentation
     → [Rules Engine + ML Risk Classifier] → Risk Report → RAG Explanation → Voice/Text Delivery
     → (if risky) → Case Draft Pre-fill → Intake Agent → Classifier/Router
     → Research Agent (RAG) → Drafting Agent → Lawyer Dashboard (human gate)
     → Approved Output → User + Tracking Agent → Case Status Updates → Outcome Feedback Loop
```

Every arrow above is a real API/service boundary that needs a defined contract (request/response schema) — worth formalizing as an OpenAPI spec once you move from this document into implementation planning.

---

## 9. Cross-Cutting Concerns

### 9.1 Legal & Ethical Safeguards (critical — discuss with supervisor explicitly)
- The system must be positioned as **"legal information and triage," never "legal advice."** This distinction has real liability implications and should be reflected in UI copy, disclaimers, and the mandatory-human-review gate.
- Every AI-generated legal document must be clearly marked as a draft pending human approval, both in-app and in any exported/printed form.
- Consider whether your institution requires ethics review/IRB-style approval given this touches real legal and personal data — raise this with your supervisor early, it may affect your pilot timeline.

### 9.2 Data Privacy & Security
- Documents contain highly sensitive data (financial terms, land records, personal identifiers). Encryption at rest and in transit is non-negotiable.
- Define a data retention policy: how long are documents/case data kept, and what's the deletion/right-to-erasure flow?
- Role-based access control across all user types (end user, volunteer, lawyer, clinic admin) — a user's data should never be visible to a lawyer not assigned to their case.
- Consent flow: users must explicitly consent to their document being analyzed and (if applicable) anonymized data being used to improve models.

### 9.3 Language & Accessibility Coverage
- Decide upfront: how many languages/scripts for Semester 1 MVP? Recommend starting with 1–2 (e.g., Hindi + one regional language matching your pilot region) rather than attempting broad coverage immediately — this is a scope-control decision, and expanding language coverage later is a natural, demoable Semester 2 milestone.

### 9.4 Connectivity & Offline Considerations
- Assume intermittent/low connectivity in target villages. Design for: async processing with clear "we'll notify you when ready" UX (not blocking spinners), offline document capture with queued upload, and SMS/voice as fallback channels alongside any app UI.

### 9.5 Trust & Adoption
- A system judging legal documents will face justified skepticism. Consider a "why should I trust this" onboarding moment — transparency about how the system works, who verifies AI output (real lawyers), and what happens to their data.
- Partnering with a trusted local intermediary (village volunteer, NGO) for initial rollout is likely essential for adoption — pure self-serve app adoption in this context is unlikely to work alone.

---

## 10. Missing Features / Open Gaps to Address in Brainstorming

These are not yet designed and need dedicated discussion:

1. **Feedback/correction loop:** If a user or lawyer disagrees with a risk flag or draft, how is that captured and used to improve the models? Currently only loosely described (§6.7) — needs a concrete mechanism (structured feedback form + retraining/prompt-tuning pipeline).
2. **Multi-party documents:** What happens when a document involves negotiation between two parties, both of whom might use the app (e.g., a landlord and tenant both scanning the same lease)? Current design assumes single-user-initiated flow only.
3. **Version tracking for renegotiated documents:** If a user gets renegotiation suggestions (§5.6) and comes back with a revised document, is there a "compare to previous version" feature? Not yet designed.
4. **Case outcome verification:** How do you confirm a case was actually resolved (vs. just marked closed)? Needs a lightweight verification step, possibly involving the assigned lawyer confirming outcome.
5. **Abuse/misuse prevention:** Could this be used maliciously (e.g., someone scanning a document to find loopholes to exploit *someone else*, or a lawyer-side account being used to approve drafts without real review)? Needs threat-modeling discussion.
6. **Multi-state legal variation:** Scoping decision from §4.2 needs to be finalized and documented before the RAG corpus is built.
7. **Volunteer/assisted-mode account management:** How are volunteer permissions scoped? Can a volunteer see a villager's full document history, or only current session data? Privacy-vs-utility trade-off not yet resolved.
8. **Analytics/impact measurement:** How will you (and your supervisor) measure whether the product is actually working — number of documents flagged risky, number of cases resolved, time-to-resolution? Worth designing a basic analytics/impact dashboard as a feature, not an afterthought, since this will matter enormously for your final presentation/demo.

---

## 11. Suggested Improvements & Enhancements (Beyond Current Scope)

- **Community pattern alerts:** If multiple villagers in the same area flag similar risky clauses from the same lender/landlord, surface this as a pattern to the local legal aid clinic — turns individual protection into community-level early warning (a strong "wow" feature for Semester 2 if time allows).
- **Simplified plain-language contract templates:** Beyond flagging risk, offer fair, simplified template contracts for common scenarios (standard land lease, standard labor agreement) that users could proactively use instead of an ad hoc document — shifts from purely reactive to also being generative/preventive.
- **Integration with government scheme eligibility:** Given your earlier research into scheme-convergence gaps, a natural (but scope-heavy) extension is: if a legal issue relates to a scheme entitlement, cross-check eligibility for relevant government support — likely too much for 2 semesters unless treated as a clearly separate stretch module.

---

## 12. Design Decisions & Trade-offs Log

| Decision | Choice | Trade-off accepted |
|---|---|---|
| Architecture style | Modular monolith over microservices | Faster team velocity; less "distributed systems" resume flash, but far more shippable in 2 semesters |
| OCR approach | Managed API over custom-trained OCR | Faster to build, dependent on external service cost/availability; acceptable for MVP |
| Risk classification | Dual rules + ML layer | More engineering work upfront; much stronger explainability and defensibility |
| Legal corpus scope | 1–2 states initially | Limits initial coverage; avoids an unmanageable multi-jurisdiction corpus problem |
| Human review gate | Mandatory, no exceptions | Slower "time to resolution" per case; essential ethical/liability safeguard |
| Language coverage | 1–2 languages for MVP | Limits initial reach; keeps voice/NLP engineering scope realistic |

---

## 13. Technical Challenges to Flag Honestly (to Supervisor and Team)

1. **Clause segmentation on messy, non-standard real-world documents** is likely the hardest NLP problem in the whole project — informal village-level contracts don't follow clean legal-template structure.
2. **Building a legitimately annotated risk-classification dataset** is a real content-engineering effort, not just an ML task — plan for this to take real calendar time, ideally with legal-domain input (a law student collaborator or your supervisor's network would help enormously).
3. **Sourcing a real legal aid partner organization** for Phase 2's escalation network is a non-engineering dependency that could block your demo if not started early.
4. **Multilingual voice quality** for regional languages varies significantly across providers — budget time to evaluate options rather than assuming any one API "just works" well for your target language(s).
5. **Balancing async processing latency with UX** — OCR + classification + RAG generation is not instant; designing a UX that keeps users engaged/informed during processing (rather than frustrated by a spinner) is a real product design challenge, not just a technical one.

---

## 14. Semester-Wise Milestone Plan (Recap, Expanded)

**Semester 1 — Ship a complete, demoable Kavach (Phase 1 only)**
- Weeks 1–3: Finalize legal corpus scope (state/language), source real example documents (with consent/anonymization), set up shared infra (DB schema, OCR pipeline, basic auth)
- Weeks 4–8: Build OCR → type classification → clause segmentation pipeline; begin building the annotated risk dataset
- Weeks 9–13: Build rules engine + ML risk classifier; integrate Legal RAG Core for explanations
- Weeks 14–16: Voice delivery (TTS), UI polish, end-to-end testing, prepare demo

**Semester 2 — Build Nyaya Setu on top of the working Phase 1 system**
- Weeks 1–4: Intake Agent + Classifier/Router Agent, Phase 1→Phase 2 handoff mechanic
- Weeks 5–9: Research Agent (extend RAG Core for case-fact queries), Drafting Agent
- Weeks 10–12: Lawyer dashboard + human-in-the-loop verification flow, Escalation Agent
- Weeks 13–14: Tracking Agent, case lifecycle management
- Weeks 15–16: Full end-to-end testing, pilot with real partner organization if secured, final demo prep

**Critical rule to state explicitly to your supervisor:** Semester 1 must end with something fully working end-to-end (Kavach alone), not a half-built version of everything. This is your safety net and your proof of execution discipline.

---

## 15. Open Questions for the Team to Resolve Before Coding Begins

1. Which 1–2 languages and which state's law are we scoping to for MVP?
2. Do we have (or can we get) a real legal aid NGO/clinic partner for the pilot, and who owns outreach for this?
3. What's our anonymized document-sourcing strategy for building the risk-classification training dataset?
4. Which managed AI APIs (OCR, STT/TTS, LLM) are we standardizing on, and what's our budget/rate-limit ceiling for a student project?
5. What does "done" look like for the Semester 1 demo — a specific number of document types, a specific accuracy bar, a live demo with real users, or a simulated dataset walkthrough?
6. Who on the team owns the legal-content curation work (§4.2), since it's not a pure coding task and needs someone comfortable with legal reading/research?

---

*End of context document. This should be treated as version 1 — revisit and update as brainstorming sessions resolve open questions in §15 and §10.*
