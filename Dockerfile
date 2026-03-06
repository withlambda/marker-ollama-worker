# Copyright (C) 2026 withLambda
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# 1. ARG SETUP
ARG PYTORCH_VERSION=2.8.0
ARG CUDA_VERSION=12.8
ARG CUDNN_VERSION=9
ARG OLLAMA_VERSION=0.17.4
#ARG PYTHON_VERSION=3.11.13
ARG BASE_IMAGE=pytorch/pytorch:${PYTORCH_VERSION}-cuda${CUDA_VERSION}-cudnn${CUDNN_VERSION}-runtime
#ARG PYTHON_IMAGE=python:${PYTHON_VERSION}-slim

# 2. LOAD OLLAMA IMAGE
FROM ollama/ollama:${OLLAMA_VERSION} as ollama-source

# 3. INSTALL PYTHON REQUIREMENTS AS WHEELS
#FROM ${PYTHON_IMAGE} as python-builder
#
#ENV TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
#
#RUN apt-get update && apt-get install -y gcc python3-dev && \
#    rm -rf /var/lib/apt/lists/*
#
#WORKDIR /app
#COPY requirements.txt ./
## Download/Build everything into a local folder
#RUN pip install --no-cache-dir --upgrade pip && \
#    pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt

# 4. PRE-DOWNLOAD ALL MARKER & DATALAB MODELS
#FROM ${PYTHON_IMAGE} as model-downloader
#
#ARG HF_TOKEN
#
#ENV XDG_CACHE_HOME=/app/cache \
#    # Define your "alias" here
#    HF_DOWNLOAD="/usr/local/bin/hf download" \
#	HF_TOKEN=${HF_TOKEN}
#
#COPY requirements.txt ./
#
# The downloaded models cover layout, OCR, and the error detection models
# RUN mkdir -p ${XDG_CACHE_HOME} && \
#    #apt-get update && apt-get install -y \
#    #curl && \
#    #rm -rf /var/lib/apt/lists/* && \
#    #curl -LsSf https://hf.co/cli/install.sh | bash && \
#    pip install --no-cache-dir --upgrade pip && \
#    pip install --no-cache-dir huggingface_hub tqdm && \
#    # Download Surya (OCR/Layout)
#    $HF_DOWNLOAD vikp/surya_det --cache-dir ${XDG_CACHE_HOME} && \
#    $HF_DOWNLOAD vikp/surya_layout --cache-dir ${XDG_CACHE_HOME} && \
#    $HF_DOWNLOAD vikp/surya_rec --cache-dir ${XDG_CACHE_HOME} && \
#    # Download Texify (Equations)
#    $HF_DOWNLOAD vikp/texify2 --cache-dir ${XDG_CACHE_HOME} && \
#    # Download Order/Selection models
#    $HF_DOWNLOAD vikp/column_detector --cache-dir ${XDG_CACHE_HOME}
#
#    pip install --no-cache-dir --no-deps $(grep "^marker-pdf==" requirements.txt) && \
#    # We still need a few light weight tools to run the download script
#	# if marker-pdf's script requires them (usually it just needs huggingface_hub)
#    pip install --no-cache-dir huggingface_hub tqdm requests pyyaml && \
#	if [ "${STAGE}" != PROD ]; then \
#    	export TORCH_DEVICE=cpu; \
#    fi && \
#    python3 -c "from marker.converters.pdf import PdfConverter; \
#	from marker.models import create_model_dict; \
#    PdfConverter(artifact_dict=create_model_dict())"

# 5. BASE IMAGE
FROM ${BASE_IMAGE}

# 6. ENVIRONMENT SETTINGS
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    OLLAMA_HOST=0.0.0.0 \
    # Redirect caches so non-root user can read models downloaded by root
    XDG_CACHE_HOME=/app/cache \
    HF_HOME=/app/cache/huggingface \
    TORCH_HOME=/app/cache/torch

# 7. Install Ollama
COPY --from=ollama-source /usr/bin/ollama /usr/bin/ollama

# 8. APPLICATION SETUP
WORKDIR /app
COPY *.py requirements.txt entrypoint/ ./
# 9. PYTHON DEPENDENCIES
#COPY --from=python-builder /app/wheels /app/wheels

# 10. COPY PRE-DOWNLOADED MARKER & DATALAB MODELS FROM
#COPY --from=model-downloader /app/cache /app/cache

RUN mkdir -p ${XDG_CACHE_HOME} \
    # 5. SYSTEM DEPENDENCIES
    # poppler-utils: Required for PDF processing
    # tesseract-ocr: Required for OCR capabilities
    && apt-get update \
    && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    curl \
    zstd \
    gcc \
    python3-dev \
    gosu \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && python3 -c "from marker.models import create_model_dict; create_model_dict()" \
    && apt-get purge -y gcc python3-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# 11. Create Non-Root User
# We create a user named 'appuser' with UID 1000
RUN	groupadd -r appgroup && useradd -r -g appgroup -u 1000 -m -d /home/appuser appuser && \
    # Fix permissions: Ensure appuser owns the app and cache
    chown -R appuser:appgroup /app /home/appuser && \
    chmod +x entrypoint.sh

# 12. START COMMAND
CMD [ "./entrypoint.sh" ]
