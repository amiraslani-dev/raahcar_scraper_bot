# 🚗 Raahcar Scraper Bot

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg?logo=python)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED.svg?logo=docker)](https://www.docker.com/)
[![Celery](https://img.shields.io/badge/Celery-Distributed%20Tasks-37814A.svg?logo=celery)](https://docs.celeryq.dev/)
[![Redis](https://img.shields.io/badge/Redis-7.x-DC382D.svg?logo=redis)](https://redis.io/)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Computer%20Vision-FF6F00.svg)](https://ultralytics.com/)
[![License: Proprietary](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)

An autonomous, distributed web scraper and computer vision pipeline tailored for car ad ingestion. It scrapes automobile listings, processes vehicle photos through an AI multi-model ensemble to locate and redact license plates with branded badges, enhances photos for SEO uniqueness, and pushes the sanitized data to the central Raahcar backend.

---

## 🌟 Key Features

- **Automated Listing Ingestion**: Fetches vehicle advertisements (Bama marketplace) respecting fuel quotas (Gasoline, CNG, Hybrid, Electric).
- **Dynamic Configuration Sync**: Periodically polls the main Raahcar server for scraping quotas and delay intervals configured by administrators in Django Admin.
- **AI-Powered Plate Redaction**: Multi-model vision pipeline (`YOLOv8` + `ONNX`) detecting:
  - Iranian standard civilian & commercial license plates.
  - Dealership / showroom vanity plates.
  - Partially covered / censored license plates.
- **Automated Branding & SEO Enhancement**:
  - Overlays custom Raahcar branding badge seamlessly over license plate locations.
  - Injects top-right corner branding watermark (`logo.webp`).
  - Applies subtle SEO zoom (5% center crop) to ensure image uniqueness across search engines.
  - Converts images to lightweight, web-optimized `.webp` format.
- **Distributed & Scheduled Architecture**:
  - **Celery Worker**: Asynchronous ad processing, download handling, image manipulation, and API posting.
  - **Celery Beat**: Built-in scheduler triggering automated daily scraping jobs (default: 08:00 AM Tehran time).
  - **Redis**: Fast message queuing and task state persistence.
  - **Flower**: Real-time web-based monitoring dashboard for tasks and workers.
- **Clean Execution Footprint**: Automatic per-ad temporary scratch directory deletion ensures zero disk bloat.

---

## 🏗️ Architecture

```mermaid
flowchart TD
    subgraph Scheduling & Orchestration
        CB[Celery Beat\nDaily Scheduler 08:00 AM] -->|Enqueue Batch| R[(Redis Broker & State)]
        CLI[main.py CLI / Manual Run] -->|Enqueue Task| R
    end

    subgraph Distributed Processing
        R --> CW[Celery Worker Pool]
        CW -->|1. Fetch Listing & Images| SCR[Bama Scraper Module]
        SCR -->|2. Raw Images| CV[AI Vision Engine\nYOLOv8 & ONNX Ensemble]
        CV -->|3. Redact Plate & Overlay Brand| CV
        CV -->|4. SEO Zoom & WebP Conversion| PUB[Publisher Module]
    end

    subgraph Raahcar Platform
        PUB -->|Multipart POST\nX-API-KEY| API[Main Server API\n/cars/api/internal/ingest/]
        PUB -->|Fetch Quotas| CFG[Config Endpoint\n/bot-manager/api/config/]
    end

    subgraph Observability
        R <--> FL[Flower Dashboard\nPort: 5555]
    end
```

---

## 📁 Repository Structure

```text
scraper_bot/
├── .github/workflows/            # Automated GitHub Actions CI/CD workflows
│   └── ci-cd.yml                 # Lint, test, docker build & VPS auto-deploy pipeline
├── assets/                       # AI models, default logos, and visual assets
│   ├── cars_best_v26.pt          # YOLOv8 Car & Contextual plate detector (~20 MB)
│   ├── plate_covered_yolov8n.pt  # Dealer / covered plate detector (~6 MB)
│   ├── plate_detector.onnx       # General license plate detector (~12 MB)
│   ├── plate_slot_yolov8n.onnx   # Plate slot detector (~12 MB)
│   ├── plate_yolo_iran.onnx      # Iranian standard plate detector (~12 MB)
│   └── logo.png                  # Plate badge replacement logo
├── tests/                        # Automated smoke & pipeline unit tests
│   ├── __init__.py
│   └── test_pipeline.py          # AI models, config, and vision pipeline tests
├── config.py                     # Central configuration & path resolvers
├── scraper.py                    # Marketplace scraper & quota logic
├── image_processor.py            # YOLOv8/ONNX detection, branding, SEO zoom
├── publisher.py                  # Multipart HTTP client & temp cleanup
├── celery_app.py                 # Celery application & Beat schedule
├── tasks.py                      # Celery tasks with exponential retries
├── main.py                       # CLI execution entrypoint (celery / direct)
├── logo.webp                     # Corner watermark branding
├── Dockerfile                    # Container definition (Python 3.12-slim + OpenCV)
├── docker-compose.yml            # Multi-service setup (Redis, Worker, Beat, Flower)
├── requirements.txt              # Production Python dependencies
├── .env.example                  # Environment configuration template
├── .gitignore                    # Git exclusion rules
└── .dockerignore                 # Docker build context optimization rules
```

---

## ⚡ Quickstart with Docker (Recommended)

### 1. Prerequisites
- [Docker](https://docs.docker.com/get-docker/) (20.10+)
- [Docker Compose](https://docs.docker.com/compose/) (v2.0+)

### 2. Configure Environment
Copy the example environment file and update the settings:
```bash
cp .env.example .env
```

Edit `.env` to point to your main Raahcar server:
```ini
MAIN_SERVER_URL=https://your-domain.com
INGESTION_API_KEY=your-secure-internal-key-2026
REDIS_URL=redis://redis:6379/0
FLOWER_PORT=5555
FLOWER_BASIC_AUTH=admin:your_secure_password
```

### 3. Build & Run
Start all services in detached mode:
```bash
docker compose up -d --build
```

This launches four interconnected containers:
1. **`raahcar_redis`**: Redis 7 message broker with persistence.
2. **`raahcar_celery_worker`**: Background worker running AI processing & publishing.
3. **`raahcar_celery_beat`**: Automated cron scheduler (08:00 AM daily).
4. **`raahcar_flower`**: Real-time web dashboard accessible at `http://localhost:5555`.

### 4. Check Service Status
```bash
docker compose ps
docker compose logs -f celery_worker
```

### 5. Trigger a Test Job via Docker
To trigger a quick test run (1 car per fuel type) inside the running worker:
```bash
docker compose exec celery_worker python main.py --mode celery --test
```

---

## 💻 Local / Standalone Development Setup

If you prefer to run the bot outside Docker for development or testing:

### 1. System Dependencies
Install OpenCV and Pillow prerequisites:
- **Ubuntu/Debian**:
  ```bash
  sudo apt-get update && sudo apt-get install -y libgl1 libglib2.0-0 libgomp1
  ```
- **Windows / macOS**:
  Pre-built wheels in `opencv-python-headless` usually handle dependencies automatically.

### 2. Python Virtual Environment
```bash
python -m venv .venv

# On Linux / macOS:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure `.env`
Ensure Redis is running locally:
```bash
redis-server
```
And set `REDIS_URL=redis://127.0.0.1:6379/0` in your `.env`.

### 4. Running the Scraper
You can execute `main.py` in two different modes:

#### A. Direct Mode (Sequential, without Celery)
Useful for rapid local testing and debugging:
```bash
# Quick test run (4 cars: gasoline, CNG, electric, hybrid)
python main.py --mode direct --test

# Full run with custom delay between ads (in seconds)
python main.py --mode direct --delay 60
```

#### B. Celery Mode (Distributed Queue)
Start a worker in one terminal:
```bash
celery -A celery_app worker --loglevel=info --concurrency=2
```
In another terminal, dispatch the batch job:
```bash
python main.py --mode celery
```

---

## ⚙️ Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `MAIN_SERVER_URL` | `http://127.0.0.1:8000` | Target Raahcar backend URL. |
| `INGESTION_API_KEY` | `raahcar-secure-bot-key-2026` | Shared secret header (`X-API-KEY`) for authenticating internal ingestion requests. |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | Connection string for Redis broker and Celery backend. |
| `DEFAULT_TARGET_COUNT` | `300` | Fallback daily ad count if server configuration is unavailable. |
| `DEFAULT_DELAY_SECONDS` | `72` | Fallback interval (seconds) between sequential ad publishings. |
| `FLOWER_PORT` | `5555` | Port for the Flower web dashboard. |
| `FLOWER_BASIC_AUTH` | `admin:raahcar2026` | HTTP Basic Auth credentials (`user:password`) for Flower. |

---

## 🧠 AI Plate Detection Pipeline

The image processor uses a multi-tiered ensemble approach:

1. **Detection**:
   - `plate_yolo_iran.onnx`: Highly optimized Iranian license plate detector.
   - `cars_best_v26.pt`: Full-car contextual model detecting bumper regions and plate slots.
   - `plate_covered_yolov8n.pt`: Specialized model trained on white paper, tape, and cloth coverings placed over plates by car sellers.
   - `plate_detector.onnx`: General plate detector fallback.
2. **Badge Overlay**:
   - Calculates bounding box aspect ratio, orientation, and perspective angle.
   - Dynamically scales and positions `assets/logo.png` over the plate area.
3. **SEO Post-Processing**:
   - Applies 5% center zoom crop to avoid duplicate image penalties on search engines.
   - Overlays `logo.webp` watermark on the top-right corner.
   - Compresses output to `.webp` format (quality 85) for optimal performance.

---

## 📊 Flower Monitoring Dashboard

When running with Docker Compose, navigate to:
```text
http://localhost:5555
```
Log in using credentials specified in `FLOWER_BASIC_AUTH` (default: `admin` / `raahcar2026`).

You can inspect:
- Active, processed, failed, and retried tasks.
- Worker CPU/Memory utilization and concurrency.
- Detailed task exception tracebacks and runtime arguments.

---

## 🔒 Security & Best Practices

- **Never commit `.env`**: Always configure production secrets via deployment variables or secret managers.
- **Firewall Flower & Redis**: In production, do NOT expose ports `6379` (Redis) and `5555` (Flower) to public traffic. Bind them to `127.0.0.1` or keep them behind a reverse proxy (e.g. Nginx with SSL & IP whitelisting).
- **Graceful Retries**: Network failures automatically trigger exponential backoff retries (`max_retries=5`, backoff factor up to 10 minutes) before marking a task as failed.

---

## 🚀 CI/CD & Automated Deployment (GitHub Actions)

The repository includes an enterprise-ready GitHub Actions pipeline (`.github/workflows/ci-cd.yml`) that guarantees code quality and automated zero-downtime deployment:

```mermaid
flowchart LR
    A[git push / PR] --> B[1. Ruff Lint & Syntax]
    B --> C[2. Pipeline & Model Tests]
    C --> D[3. Docker Buildx & Cache]
    D -->|Push to main only| E[4. SSH Deploy to VPS]
    E --> F[docker compose up -d]
```

### 1. Pipeline Stages
- **Lint Stage**: Uses Ruff for instant AST-level syntax and broken import checks.
- **Test Stage**: Installs OpenCV/ONNX dependencies and executes `tests/test_pipeline.py` (verifying model weights, config, and synthetic image transformation).
- **Docker Stage**: Builds the Docker container with GitHub Actions Layer Cache (`type=gha`) to ensure the Dockerfile compiles without runtime errors.
- **Deploy Stage**: Connects securely via SSH to the production VPS, pulls the latest commits, updates containers via `docker compose up -d --remove-orphans`, prunes dangling images, and verifies health status.

### 2. Required GitHub Secrets
Under your GitHub Repository **Settings -> Secrets and variables -> Actions**, add:

| Secret Name | Description | Example |
|---|---|---|
| `SERVER_HOST` | Production VPS IP address or hostname | `185.x.x.x` |
| `SERVER_USER` | Remote SSH username | `deploy` or `root` |
| `SERVER_SSH_KEY` | Private SSH Key (ed25519 or RSA) | `-----BEGIN OPENSSH PRIVATE KEY...` |
| `SERVER_PORT` | SSH Port (optional, defaults to 6579) | `6579` or `22` |
| `SCRAPER_PROJECT_PATH` | Path to scraper_bot directory on VPS | `/opt/raahcar_scraper_bot` or `/home/ubuntu/raahcar/scraper_bot` |

---

## 📜 License

Proprietary and confidential. Part of the **Raahcar** automobile platform. Unauthorized copying or redistribution is strictly prohibited.
