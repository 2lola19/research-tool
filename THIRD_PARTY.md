# Third-Party Dependencies

This ledger covers dependencies incorporated into the executable foundation. Candidate scientific components are evaluated separately in `docs/OPEN_SOURCE_COMPONENTS.md`.

| Dependency | Upstream | License | Purpose | Integration |
|---|---|---|---|---|
| FastAPI | https://github.com/fastapi/fastapi | MIT | HTTP API and OpenAPI | Python package |
| Pydantic / pydantic-settings | https://github.com/pydantic/pydantic | MIT | Validation and typed configuration | Python packages |
| SQLAlchemy | https://github.com/sqlalchemy/sqlalchemy | MIT | Relational persistence abstraction | Python package |
| Alembic | https://github.com/sqlalchemy/alembic | MIT | Schema migrations | Python package |
| psycopg | https://github.com/psycopg/psycopg | LGPL-3.0 | PostgreSQL driver | Binary Python package; replaceable behind SQLAlchemy |
| FastAPI/Uvicorn | https://github.com/encode/uvicorn | BSD-3-Clause | ASGI development/runtime server | Python package |
| Next.js | https://github.com/vercel/next.js | MIT | Web application framework | npm package, App Router |
| React | https://github.com/facebook/react | MIT | UI rendering | npm package |
| Tailwind CSS | https://github.com/tailwindlabs/tailwindcss | MIT | Design tokens and utility styling | npm build integration |
| Ruff | https://github.com/astral-sh/ruff | MIT | Python linting/formatting | Development-only tool |
| mypy | https://github.com/python/mypy | MIT | Python static type checking | Development-only tool |
| pytest | https://github.com/pytest-dev/pytest | MIT | Backend tests | Development-only tool |
| Vitest | https://github.com/vitest-dev/vitest | MIT | Frontend unit tests | Development-only tool |

No third-party source is vendored or modified in this milestone.

