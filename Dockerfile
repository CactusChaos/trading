FROM python:3.12-slim

# Install git, gcc, and build essentials for arm64/asahi compatibility
RUN apt-get update && apt-get install -y git gcc g++ python3-dev build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir uv
RUN uv pip install --system -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Start server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
