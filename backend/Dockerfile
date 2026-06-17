FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Bundle local DB and metadata so Railway volume mounts do not hide them
RUN cp -r chroma_db bundled_chroma_db && cp -r tmp bundled_tmp

# Railway injects $PORT at runtime. We expose 8080 here only as documentation;
# the actual bound port is always whatever $PORT resolves to at startup.
EXPOSE 8080

CMD ["python", "main.py"]