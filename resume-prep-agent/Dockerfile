FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (fonts for clean ATS PDF generation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    fonts-liberation \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV PORT=8001

EXPOSE 8001

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8001"]

