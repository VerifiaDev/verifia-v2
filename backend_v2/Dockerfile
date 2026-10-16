# Build from the REPO ROOT (it needs ai-engine/ai_engine.py):
#     docker build -f backend_v2/Dockerfile -t verify-backend .
#
# No torch, no sentence-transformers, no Chromium -> small image, fits in 512 MB.

FROM python:3.12-slim

WORKDIR /app

COPY backend_v2/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Single source of truth for the two modules we reuse (never copied into backend_v2/)
COPY ai-engine/ai_engine.py ./ai_engine.py
COPY retrieval_demo_lite/search_retrieval_lite.py ./search_retrieval_lite.py
COPY backend_v2/app ./app

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
