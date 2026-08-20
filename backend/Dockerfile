FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install --only-upgrade -y --no-install-recommends \
        bsdutils \
        libblkid1 \
        liblastlog2-2 \
        libmount1 \
        libsmartcols1 \
        libuuid1 \
        login \
        mount \
        util-linux \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system --gid 1001 app && adduser --system --uid 1001 --ingroup app app

COPY pyproject.toml README.md alembic.ini ./
COPY backend ./backend
COPY workers ./workers
RUN python -m pip install --no-cache-dir . \
    && python -m pip uninstall --yes pip \
    && rm -rf /usr/local/lib/python3.13/ensurepip /root/.cache

RUN mkdir -p /app/data/objects && chown -R app:app /app
USER app

EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

HEALTHCHECK --interval=10s --timeout=5s --retries=12 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready')"
