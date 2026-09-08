# Production Deployment & Containerization Guide

This guide outlines how to build, containerize, and deploy the **Job Market Pulse** platform across cloud platforms and container environments.

> **100% Free Cloud Deployment**: For zero cost and zero local computer dependencies, see the [**Streamlit Community Cloud Deployment Guide**](FREE_STREAMLIT_DEPLOYMENT_GUIDE.md).

---

## 1. Quickstart: Local Docker Deployment

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) (version 24+)
- [Docker Compose](https://docs.docker.com/compose/)
- An active `.env` file with Databricks credentials.

### Step 1: Prepare Environment
Ensure your `.env` file exists in the repository root (use `.env.example` as a template):
```bash
cp .env.example .env
# Edit .env with your DATABRICKS_HOST, DATABRICKS_HTTP_PATH, and DATABRICKS_TOKEN
```

### Step 2: Build and Run with Docker Compose
```bash
# Build the image and start the container in background
docker compose up -d --build

# Inspect container status and health
docker compose ps

# View live application logs
docker compose logs -f
```

Access the web interface at **`http://localhost:8501`**.

### Step 3: Run with Pure Docker (Without Compose)
```bash
# Build the image
docker build -t job-market-pulse:latest .

# Run container with environment file and volume mount
docker run -d \
  --name job-market-pulse \
  -p 8501:8501 \
  --env-file .env \
  -v $(pwd)/exports:/app/exports \
  job-market-pulse:latest
```

---

## 2. Cloud Deployment Targets

### Option A: AWS App Runner / ECS (Fargate)
1. **Push image to AWS ECR**:
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <aws_account_id>.dkr.ecr.us-east-1.amazonaws.com
   docker tag job-market-pulse:latest <aws_account_id>.dkr.ecr.us-east-1.amazonaws.com/job-market-pulse:latest
   docker push <aws_account_id>.dkr.ecr.us-east-1.amazonaws.com/job-market-pulse:latest
   ```
2. **Deploy via App Runner**:
   - Source: Container registry (`ECR`).
   - Port: `8501`.
   - Environment variables: Inject `DATABRICKS_HOST`, `DATABRICKS_HTTP_PATH`, `DATABRICKS_TOKEN`.
   - Auto-scaling: 1-5 instances based on request concurrency.

### Option B: Google Cloud Run
1. **Build and submit to Google Artifact Registry**:
   ```bash
   gcloud builds submit --tag gcr.io/<project-id>/job-market-pulse
   ```
2. **Deploy Service**:
   ```bash
   gcloud run deploy job-market-pulse \
     --image gcr.io/<project-id>/job-market-pulse \
     --platform managed \
     --port 8501 \
     --set-env-vars DATABRICKS_HOST=$DATABRICKS_HOST,DATABRICKS_HTTP_PATH=$DATABRICKS_HTTP_PATH,DATABRICKS_TOKEN=$DATABRICKS_TOKEN \
     --allow-unauthenticated
   ```

### Option C: Virtual Private Server (VPS / EC2 / DigitalOcean)
1. Install Docker & Nginx.
2. Clone repository and run `docker compose up -d`.
3. Configure Nginx reverse proxy with SSL (`certbot` / Let's Encrypt):
   ```nginx
   server {
       server_name jobs.yourdomain.com;

       location / {
           proxy_pass http://localhost:8501;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

---

## 3. Production Hardening Checklist
- [x] Multi-stage build with Astral `uv` for 10x faster image assembly.
- [x] Healthcheck probe configured at `/_stcore/health`.
- [x] Sensitive tokens excluded via `.dockerignore`.
- [x] Streamlit usage stats disabled in `.streamlit/config.toml`.
- [x] Volume mount configured for persistent cold-storage exports (`/app/exports`).
