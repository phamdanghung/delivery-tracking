FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace
COPY apps/api/requirements.lock apps/api/requirements.lock
RUN pip install --no-cache-dir -r apps/api/requirements.lock
COPY apps/api apps/api
COPY db db
RUN useradd --uid 10001 --create-home fleet
USER fleet
WORKDIR /workspace/apps/api
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log"]
