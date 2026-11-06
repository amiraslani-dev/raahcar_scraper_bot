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

# Build arguments for PyPI mirror (defaults to high-speed Tsinghua mirror with official PyPI fallback)
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_EXTRA_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

# Copy and install python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir \
    --default-timeout=180 \
    -i ${PIP_INDEX_URL} \
    --extra-index-url ${PIP_EXTRA_INDEX_URL} \
    --trusted-host ${PIP_TRUSTED_HOST} \
    --trusted-host pypi.org \
    -r requirements.txt

# Copy source code
COPY . /app/

CMD ["celery", "-A", "celery_app", "worker", "--loglevel=info", "--concurrency=2"]
