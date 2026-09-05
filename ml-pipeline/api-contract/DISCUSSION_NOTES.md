# API Contract - Discussion Notes for Backend Sync

The full spec is in `openapi.yaml` (same folder). Three things need a real
conversation with the Java team before this is final - don't just implement
against the spec silently, these decisions affect both sides.

## 1. Who determines `doc_type`?

The roadmap only covers **clause-level** classification (Stage 1.3's
fine-tuned IndicBERT). There is no whole-**document**-type classifier in the
plan. That means either:
- **(Recommended for MVP)** The user selects document type during upload in
  the app (a simple dropdown: "Loan/Chit", "Land Lease", "Labor Contract"),
  and Java always sends `doc_type_hint` populated.
- Or: we build a second, separate classifier just for document type - real
  extra work not currently scoped anywhere in the roadmap.

**Ask the backend/frontend team**: is a manual doc-type selection at upload
already planned in the UI? If yes, this is a non-issue.

## 2. Synchronous or async?

Roadmap Stage 4.1 explicitly says the processing UI must be "async/polling,
not a blocking spinner" - which implies the full pipeline (segment ->
classify -> RAG -> LLM call for judgment cases) might be too slow for a
simple synchronous request/response.

**Two options to discuss:**
- Simple synchronous `POST /analyze-document` (as currently specced) - fine
  if end-to-end processing lands under a few seconds once measured for real.
- Async pattern: `POST /analyze-document` returns `202 Accepted` + a job ID
  immediately, Java polls `GET /analyze-document/{job_id}` until status is
  `complete`. More resilient, matches the roadmap's own UI guidance, more
  work to build.

**Recommendation**: start synchronous for the MVP demo, measure real latency
once the pipeline exists end-to-end, switch to async only if latency actually
requires it. Don't build the async version speculatively.

## 3. Error handling expectations

What should Java do on a `422` (unsupported doc type / empty text) vs `500`
(pipeline crashed)? Does Java retry, show the user a specific message, or
fall back to "manual review needed"? This affects what `error_code` values
are actually useful to return - the three in the spec (`unsupported_doc_type`,
`empty_text`, `pipeline_failure`) are a starting guess, not final.
