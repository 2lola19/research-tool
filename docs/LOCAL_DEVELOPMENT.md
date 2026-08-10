# Local Development

Docker Compose is the reproducible default. It runs PostgreSQL, a one-shot migration, FastAPI, the background worker process, and Next.js. Source-mounted hot reload profiles can be added after core domains stabilize; the default compose path mirrors production container boundaries.

Native Windows development uses a repository-local `.venv` and the frontend's npm lock file. Configuration is read from `.env`, which is ignored by Git. `.env.example` documents every supported setting without credentials.

Useful endpoints:

- `GET http://localhost:8000/health/live`: process liveness.
- `GET http://localhost:8000/health/ready`: database readiness.
- `GET http://localhost:8000/api/v1/system/info`: non-secret runtime metadata.
- `GET http://localhost:3000/api/health`: frontend liveness.

