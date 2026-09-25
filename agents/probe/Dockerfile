FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DEVICEMESH_PROBE_QUEUE_PATH=/data/results.sqlite3
WORKDIR /app
COPY pyproject.toml .
COPY devicemesh_probe ./devicemesh_probe
RUN pip install --no-cache-dir . && useradd --uid 10001 probe && mkdir /data && chown probe /data
USER 10001
VOLUME ["/data"]
CMD ["python", "-m", "devicemesh_probe", "--synthetic"]
