# Deployment

Local demo: run `docker compose up --build`, then open
`http://localhost:8000`. Data persists in named volumes.

Production: build the image in CI, scan it, deploy behind TLS, replace demo
authentication, use PostgreSQL, mount encrypted object storage, set backups,
health probes and resource limits. Do not expose port 8000 directly.

Backup SQLite demo data by stopping the container and copying `aicc.db`.
Restore only into the same tested application version. PostgreSQL production
deployments should use `pg_dump` plus periodic restore drills.
