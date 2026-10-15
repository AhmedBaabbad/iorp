# IORP backend — production image (PHASE-4).
# Reproducible: pinned runtime digest + hashed lock (requirements.lock, generated from pyproject.toml for linux/py3.12).
# No secrets, no .env, no uploads, no tests in the runtime image. Runs as an unprivileged user without --reload.

ARG PYTHON_IMAGE=python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258

FROM ${PYTHON_IMAGE} AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

FROM base AS deps
COPY requirements.lock ./
RUN pip install --require-hashes --no-deps -r requirements.lock

# Test image for CI: same runtime and locked dependencies, plus the dev lock and the tests.
FROM deps AS test
COPY requirements-dev.lock ./
RUN pip install --require-hashes --no-deps -r requirements-dev.lock
COPY alembic.ini pyproject.toml ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
COPY tests ./tests
ENV APP_ENV=test DEBUG=false EMAIL_MODE=console RUN_POSTGRES_TESTS=0 PRODUCTION_AUTO_START_BY_DATE=false \
    DATABASE_URL=postgresql+psycopg://unused:unused@127.0.0.1:1/isolated_unreachable
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]

FROM deps AS runtime
RUN groupadd --system --gid 10001 iorp \
 && useradd --system --uid 10001 --gid iorp --home-dir /app --shell /usr/sbin/nologin iorp \
 && mkdir -p /var/lib/iorp/uploads \
 && chown iorp:iorp /var/lib/iorp/uploads
COPY --chown=root:root alembic.ini pyproject.toml ./
COPY --chown=root:root alembic ./alembic
COPY --chown=root:root app ./app
COPY --chown=root:root scripts/backup ./scripts/backup
ENV APP_ENV=production \
    UPLOADS_DIR=/var/lib/iorp/uploads \
    PORT=8080
USER iorp
EXPOSE 8080
VOLUME ["/var/lib/iorp/uploads"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=4).status == 200 else 1)"
# One process: the login/refresh rate limiter is in-process (see the deployment plan before adding workers).
# Proxy headers are evaluated by the application itself against TRUSTED_PROXY_IPS.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-server-header"]
