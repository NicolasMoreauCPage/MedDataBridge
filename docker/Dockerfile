FROM python:3.11-slim

WORKDIR /app

# ``requirements.txt`` is the single dependency manifest used by local work,
# CI and this image. libpq is required by psycopg's PostgreSQL binary package.
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data /app/logs \
    && useradd --create-home --shell /usr/sbin/nologin app \
    && chown -R app:app /app

USER app
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health', timeout=5)" || exit 1

ENTRYPOINT ["/bin/sh", "/app/docker/entrypoint.sh"]
# Un seul worker tant que les écouteurs MLLP et le planificateur ne sont pas
# coordonnés entre processus : chacun est démarré dans le lifespan FastAPI.
CMD ["python", "-m", "uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "8000"]
