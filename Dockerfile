FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies for OpenCV and Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Build arguments for PyPI mirror (defaults to official PyPI for global CI/CD runners)
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=pypi.org

# Copy and install python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir \
    --default-timeout=120 \
    -i ${PIP_INDEX_URL} \
    --trusted-host ${PIP_TRUSTED_HOST} \
    -r requirements.txt

# Copy source code
COPY . /app/

CMD ["celery", "-A", "celery_app", "worker", "--loglevel=info", "--concurrency=2"]
