FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd --gid 10001 devicemesh && useradd --uid 10001 --gid 10001 --no-create-home devicemesh
COPY pyproject.toml .
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app
RUN pip install --no-cache-dir --no-deps .
USER 10001:10001
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
