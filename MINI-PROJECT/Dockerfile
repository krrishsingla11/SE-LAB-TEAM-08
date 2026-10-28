FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --default-timeout=120 --retries=5 -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "-c", "from app import create_app; app = create_app(); app.run(host='0.0.0.0', port=5000)"]