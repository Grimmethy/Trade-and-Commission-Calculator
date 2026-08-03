FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY scripts/ scripts/
COPY data/ data/

ENV DATABASE_PATH=/data/trade.db
ENV PHOTOS_DIR=/data/photos
ENV EXPORTS_DIR=/data/exports
ENV PRINT_ENABLED=false

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
