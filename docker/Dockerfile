# Multi-stage Dockerfile pour MedBridge
# Stage 1: Build stage
FROM python:3.11-slim as builder

# Installer les dépendances système pour la compilation
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Créer un utilisateur non-root
RUN useradd --create-home --shell /bin/bash app

# Créer le répertoire de l'application
WORKDIR /app

# Copier les fichiers de dépendances
COPY pyproject.toml poetry.lock* requirements*.txt ./

# Installer Poetry
RUN pip install --no-cache-dir poetry

# Configurer poetry pour ne pas créer d'environnement virtuel
RUN poetry config virtualenvs.create false

# Installer les dépendances
RUN poetry install --no-dev --no-interaction --no-ansi

# Stage 2: Production stage
FROM python:3.11-slim as production

# Installer les dépendances runtime
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Créer un utilisateur non-root
RUN useradd --create-home --shell /bin/bash app

# Créer les répertoires nécessaires
RUN mkdir -p /app /app/data /app/logs && \
    chown -R app:app /app

# Copier les dépendances installées depuis le builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Changer d'utilisateur
USER app

# Définir le répertoire de travail
WORKDIR /app

# Copier le code de l'application
COPY --chown=app:app . .

# Variables d'environnement
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Exposer le port
EXPOSE 8000

# Commande de démarrage
CMD ["python", "-m", "uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]