# Test coverage and acceptance status

Automated tests cover ISBN-10/13 validation, invalid identifiers, Cutter
variation, personal/corporate MARC main entries, 245 structure, control fields,
MARCXML parsing, draft-before-approval, search and statistics.

Working MVP: upload preview, OCR fallback, evidence/confidence, ISBN validation,
classification suggestions, MARC JSON/XML, duplicate check, QA, human approval,
version snapshot, local search, chat, reports, audit and Docker.

Production integrations not bundled: licensed DDC/LCC data, institutional ILS,
PostgreSQL/pgvector, external authority services, OIDC and remote LLM.

Version 4 agent verification also covers: Arabic fuzzy catalog search, language
and year filters, missing-field reports, duplicate ISBN detection, RAG retrieval
with citations, MARC knowledge answers, and strict out-of-scope rejection.

Version 5 verification adds multi-render OCR, objective capture-quality metrics,
evidence-conflict blocking, checksum-only OCR repair for ISBN, expanded DDC/LCC
topic rules, and stricter MARC 245/264/300 validation. Eight automated core
tests pass.

Version 5.1 performance fix reduces OCR from twelve passes to two complementary
passes per image, processes up to three images concurrently, caps each OCR pass
at 25 seconds, and adds a browser-side three-minute fail-safe.

Version 6 adds the professional cataloging coordinator: RDA element mapping,
authorized access-point selection, subject/classification decisions, evidence
mapping, capture remediation tasks, expanded MARC RDA fields, and hard approval
gates. Eleven automated tests pass.

Version 6.1 removes unsafe author guessing, requires independent evidence for
unlabelled titles, rejects conflicting publication years, verifies valid ISBNs
against Open Library with Google Books fallback, records OCR/source conflicts,
and accepts externally supplied DDC/LCC only when attached to the same ISBN.
Thirteen core tests pass.

Version 7 sends book-page images to OpenAI Vision through the Responses API and
requires a strict 39-element bibliographic JSON record. Every accepted Vision
field must have image evidence and confidence of at least 75. ISBN checksum and
edition-source verification remain authoritative, OCR remains a fallback, and
unverified Vision DDC/LCC values are shown only as alternatives. The test suite
also validates the strict schema, evidence gates, request construction and
structured-response parsing.
