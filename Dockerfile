FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install gcc for C extensions, install Python deps, then remove gcc
COPY requirements.txt .
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get purge -y --auto-remove gcc && \
    rm -rf /var/lib/apt/lists/*

# Copy project
COPY . .

# Create directories for database and static files
RUN mkdir -p /app/db /app/static /app/staticfiles

# Collect static files at build time (uses dummy key since we only need files)
RUN DJANGO_SECRET_KEY=build-placeholder \
    DJANGO_DEBUG=False \
    DATABASE_PATH=/app/db/db.sqlite3 \
    python manage.py collectstatic --noinput

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
