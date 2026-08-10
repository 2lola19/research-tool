# Local Development

Docker Compose is the reproducible default. It runs PostgreSQL, a one-shot migration, FastAPI, the background worker process, and Next.js. Source-mounted hot reload profiles can be added after core domains stabilize; the default compose path mirrors production container boundaries.

Native Windows development uses a repository-local `.venv` and the frontend's npm lock file. Configuration is read from `.env`, which is ignored by Git. `.env.example` documents every supported setting without credentials.

Useful endpoints:

- `GET http://localhost:8000/health/live`: process liveness.
- `GET http://localhost:8000/health/ready`: database readiness.
- `GET http://localhost:8000/api/v1/system/info`: non-secret runtime metadata.
- `GET http://localhost:3000/api/health`: frontend liveness.

## Local identity bootstrap

After migrations apply, set the five `LOCAL_*` bootstrap values in the ignored `.env` file. Keep `LOCAL_ADMIN_PASSWORD` and `LOCAL_AUTH_SECRET` private. Create the initial organization owner once:

```powershell
.\.venv\Scripts\python.exe -m backend.app.identity.bootstrap
```

Obtain a short-lived token with `POST /api/v1/auth/token` using the configured email/password. Tenant endpoints require both `Authorization: Bearer <token>` and `X-Organization-ID: <organization UUID>`. The bootstrap command prints only the created user and organization identifiers, never credentials.
