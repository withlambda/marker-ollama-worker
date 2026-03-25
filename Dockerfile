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
ARG DOWNLOAD_MARKER_MODELS="false"
ARG BASE_IMAGE=pytorch/pytorch:${PYTORCH_VERSION}-cuda${CUDA_VERSION}-cudnn${CUDNN_VERSION}-runtime

# 2. BASE IMAGE
FROM ${BASE_IMAGE}

ARG DOWNLOAD_MARKER_MODELS

# 3. ENVIRONMENT SETTINGS
# -- Redirect caches so non-root user can read models downloaded by root --
#
# XDG_CACHE_HOME=/app/cache
# TORCH_HOME=/app/cache/torch
#
# --- Ensure Python always sees the GPU in the same order as the system, to avoid "device not found" errors
#
# CUDA_DEVICE_ORDER=PCI_BUS_ID
#
# --- Prevent CPU Thread Overload ---
# --- Keeps the CPU from choking while the GPU does the heavy lifting ---
#
# TORCH_NUM_THREADS=1
# OMP_NUM_THREADS=1
# MKL_NUM_THREADS=1
# OPENBLAS_NUM_THREADS=1
# VECLIB_MAXIMUM_THREADS=1
# NUMEXPR_NUM_THREADS=1
#
# --- Ensure Predictable CPU Performance ---
#
# MKL_DYNAMIC=FALSE
# OMP_DYNAMIC=FALSE
#
# --- Fix for Sequential GPU Workflows (Marker -> vLLM) ---
#
# PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"
#
# --- vLLM Engine Optimization ---
#
# NCCL_P2P_DISABLE=1

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    XDG_CACHE_HOME=/app/cache \
    TORCH_HOME=/app/cache/torch \
    CUDA_DEVICE_ORDER=PCI_BUS_ID \
    MKL_DYNAMIC=FALSE \
    TORCH_NUM_THREADS=1 \
    OMP_DYNAMIC=FALSE \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    VECLIB_MAXIMUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True" \
    NCCL_P2P_DISABLE=1

# 5. APPLICATION SETUP
WORKDIR /app
COPY requirements.txt ./

RUN mkdir -p ${XDG_CACHE_HOME} && \
    apt-get update \
    && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    curl \
    zstd \
    gcc \
    python3-dev \
    gosu \
    && pip install --no-cache-dir --break-system-packages pip  \
    && pip install --no-cache-dir --break-system-packages --use-deprecated=legacy-resolver -r requirements.txt \
    && python3 -c "from marker.util import assign_config, download_font; download_font();" \
    && if [ "${DOWNLOAD_MARKER_MODELS}" = "true" ]; then \
    	python3 -c "from marker.models import create_model_dict; create_model_dict()"; \
    fi \
    && apt-get purge -y gcc python3-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY *.py block_correction_prompts.json ./

# 8. Create Non-Root User (UID 1001) with the name appuser
# Ensure appuser owns the app and cache
RUN	groupadd -r appgroup && useradd -r -g appgroup -u 1001 -m -d /home/appuser appuser && \
    chown -R appuser:appgroup /app /home/appuser

ENV HANDLER_FILE_NAME="handler.py"

# 9. START COMMAND
CMD python3 -u  "${HANDLER_FILE_NAME}"
