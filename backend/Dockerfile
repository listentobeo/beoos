FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY backend/pyproject.toml ./
COPY backend/app ./app
COPY backend/prompts ./prompts
COPY backend/alembic.ini ./
COPY database /database
RUN pip install --upgrade pip && pip install .

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
