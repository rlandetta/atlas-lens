FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY app ./app

EXPOSE 5101

CMD ["sh", "-c", "AYAMPI_DEV_HOST=${AYAMPI_CONTAINER_HOST:-0.0.0.0} python app.py"]
