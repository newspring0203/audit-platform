FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 AUDIT_MODE=demo AUDIT_RUNTIME_ROOT=/tmp/audit-platform
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt && useradd --create-home --uid 10001 audit
COPY --chown=audit:audit backend backend
COPY --chown=audit:audit src src
COPY --chown=audit:audit frontend frontend
COPY --chown=audit:audit scripts/run_server.py scripts/run_server.py
COPY --chown=audit:audit data/demo data/demo
USER audit
EXPOSE 8000
CMD ["python", "scripts/run_server.py"]
