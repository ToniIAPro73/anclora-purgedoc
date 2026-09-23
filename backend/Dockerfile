FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgomp1 \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10003 --shell /usr/sbin/nologin app

WORKDIR /app
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY backend /app/backend

RUN mkdir -p /tmp/anclora-purgedoc && chown -R app:app /tmp/anclora-purgedoc /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=15s --start-period=120s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=10)"
CMD ["uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "8000"]
