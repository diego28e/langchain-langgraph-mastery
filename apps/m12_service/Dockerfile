# syntax=docker/dockerfile:1
# The Orbita Cloud support desk as a container image (Lesson 12.06).
# Build from the repository root (the context needs pyproject.toml, src/ and data/):
#   docker build -f apps/m12_service/Dockerfile -t mastery-m12-service:dev .
# VERIFIED 2026-10-16: python:3.12-slim on Docker Hub (Debian trixie), the course's tested Python.

# ---- build stage: compilers and pip caches stay here, not in the final image ----
FROM python:3.12-slim AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
WORKDIR /build
# Dependencies first: this layer is reused until pyproject.toml or the lock changes.
COPY pyproject.toml ./
COPY constraints/ constraints/
COPY src/ src/
RUN pip install -c constraints/constraints-2026-10-16.txt ".[llm,memory,service]"

# ---- runtime stage: the venv, the app and its sample data; no source tree, no compilers ----
FROM python:3.12-slim
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    LC_MASTERY_ROOT=/app MASTERY_SERVICE_LOG_FORMAT=json MASTERY_SERVICE_LOG_LEVEL=INFO
RUN useradd --create-home --uid 10001 app
COPY --from=build /opt/venv /opt/venv
WORKDIR /app
# find_repo_root() looks for these two files; the desk reads its customers and FAQ from data/.
COPY pyproject.toml COURSE_OUTLINE.md ./
COPY data/samples/support-desk/ data/samples/support-desk/
COPY apps/m12_service/ apps/m12_service/
RUN mkdir -p data/outputs && chown app:app data/outputs
USER app
EXPOSE 8000
# Docker marks the container unhealthy when /ready fails (slim has no curl: use Python).
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=2).status != 200)"]
# Exec form: uvicorn is PID 1 and receives SIGTERM itself. It stops accepting connections, waits up
# to 10 s for open ones (streams), then the app drains runs for MASTERY_SERVICE_DRAIN_S.
CMD ["uvicorn", "apps.m12_service.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--timeout-graceful-shutdown", "10", "--proxy-headers", "--no-access-log"]
