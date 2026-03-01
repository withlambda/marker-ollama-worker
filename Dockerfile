# 1. ARG Setup
ARG PYTORCH_VERSION=2.8.0
ARG CUDA_VERSION=12.9
ARG CUDNN_VERSION=9
ARG OLLAMA_VERSION=0.17.4
ARG STAGE=PROD
ARG BASE_IMAGE=pytorch/pytorch:${PYTORCH_VERSION}-cuda${CUDA_VERSION}-cudnn${CUDNN_VERSION}-runtime

# 2. Load Ollama image
FROM ollama/ollama:${OLLAMA_VERSION} as ollama-source

# 3. BASE IMAGE
FROM ${BASE_IMAGE}

# 4. ENVIRONMENT SETTINGS
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    OLLAMA_HOST=0.0.0.0 \
    # Redirect caches so non-root user can read models downloaded by root
    XDG_CACHE_HOME=/app/cache \
    HF_HOME=/app/cache/huggingface \
    TORCH_HOME=/app/cache/torch

# 6. Install Ollama
COPY --from=ollama-source /usr/bin/ollama /usr/bin/ollama

# 7. APPLICATION SETUP
WORKDIR /app
COPY *.py *.txt entrypoint/ ./

RUN mkdir -p ${XDG_CACHE_HOME} && \
    # 5. SYSTEM DEPENDENCIES
    # poppler-utils: Required for PDF processing
    # tesseract-ocr: Required for OCR capabilities
    apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    curl \
    zstd \
    gcc \
    python3-dev \
    gosu \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* && \
	# 8. PYTHON DEPENDENCIES
	# Install PyTorch CPU version explicitly to keep image size small
	pip install --no-cache-dir --upgrade pip && \
    if [ "${STAGE}" != PROD ] && [ -f requirements-test.txt ]; then \
    	pip install --no-cache-dir -r requirements-test.txt; \
    fi && \
    pip install --no-cache-dir -r requirements.txt && \
	# 9. PRE-DOWNLOAD ALL MARKER & DATALAB MODELS
	# This covers layout, OCR, and the error detection models
	if [ "${STAGE}" != PROD ]; then \
    	export TORCH_DEVICE=cpu; \
    fi && \
    python3 -c "from marker.converters.pdf import PdfConverter; \
	from marker.models import create_model_dict; \
    PdfConverter(artifact_dict=create_model_dict())" && \
	# 10. Create Non-Root User
	# We create a user named 'appuser' with UID 1000
	groupadd -r appgroup && useradd -r -g appgroup -u 1000 -m -d /home/appuser appuser && \
    # Fix permissions: Ensure appuser owns the app and cache
    chown -R appuser:appgroup /app /home/appuser && \
    chmod +x entrypoint.sh

# 11. START COMMAND
CMD [ "./entrypoint.sh" ]
