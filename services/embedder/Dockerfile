# torch cu118 wheels bundle the CUDA runtime, so a slim Python base is enough;
# the node only needs the NVIDIA driver + container runtime (device plugin).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/models/hf \
    SENTENCE_TRANSFORMERS_HOME=/models/st

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the model into the image so pods start without a network pull.
ARG EMBED_MODEL=BAAI/bge-base-en-v1.5
ENV EMBED_MODEL=${EMBED_MODEL}
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBED_MODEL}')"

COPY app.py .

EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
