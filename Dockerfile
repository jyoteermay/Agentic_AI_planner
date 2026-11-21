# ---- Base image: small official Python, same version as your local env ----
FROM python:3.12-slim

# Don't write .pyc files; send print/log output straight to the terminal (no buffering)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LOG_DIR=/tmp/logs

WORKDIR /app

# ---- Dependencies first (cached layer) ----
# Code changes won't trigger a full reinstall; only requirements.txt changes do.
# "-e ." is for local development only, so strip it here.
COPY requirements.txt .
RUN grep -v '^-e' requirements.txt > /tmp/requirements.txt \
 && pip install -r /tmp/requirements.txt

# ---- Application code ----
COPY . .

# ---- Run as a non-root user (security best practice) ----
RUN useradd --create-home --uid 1000 appuser \
 && chown -R appuser /app
USER appuser

# 8000 = FastAPI, 8501 = Streamlit
EXPOSE 8000 8501

# Default command starts the API; the UI container overrides this
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
