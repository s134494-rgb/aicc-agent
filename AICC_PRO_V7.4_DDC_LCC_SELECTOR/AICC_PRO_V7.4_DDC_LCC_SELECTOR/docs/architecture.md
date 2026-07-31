# Architecture

Browser → FastAPI API → observable cataloging workflow → SQLite development
database. Specialist modules cover image validation, OCR, page detection,
evidence, metadata, ISBN, subject analysis, classification, MARC and QR.
`analysis_sessions` separates drafts from approved bibliographic records.
Approval writes an immutable snapshot to `record_versions` and an audit event.

Production target: PostgreSQL + pgvector, object storage, task queue, TLS reverse
proxy, institutional identity provider and licensed classification sources.
The local fallback remains available when an LLM or external service is absent.
