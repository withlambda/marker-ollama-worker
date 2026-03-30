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
ARG PYTORCH_VERSION=2.10.0
ARG CUDA_VERSION=12.6
ARG CUDNN_VERSION=9
ARG BASE_IMAGE=pytorch/pytorch:${PYTORCH_VERSION}-cuda${CUDA_VERSION}-cudnn${CUDNN_VERSION}-runtime

# 2. BASE IMAGE
FROM ${BASE_IMAGE}

ARG BASE_IMAGE

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
    CC=/usr/bin/gcc \
    PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True" \
    NCCL_P2P_DISABLE=1 \
    MINERU_TOOLS_CONFIG_JSON="/app/mineru.json" \
    MINERU_TOOLS_CONFIG_PATH="/app/mineru.json"

# 5. APPLICATION SETUP
WORKDIR /app
COPY requirements.txt check_dependencies.py ./

RUN mkdir -p ${XDG_CACHE_HOME} && \
    apt-get update \
    && apt-get install -y \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    curl \
    zstd \
    gcc \
    g++ \
    python3-dev \
    gosu \
    && pip install --no-cache-dir --break-system-packages pip  \
    && pip install --no-cache-dir --break-system-packages \
       paddlepaddle-gpu==3.3.0 \
       -i https://www.paddlepaddle.org.cn/packages/stable/cu126/ \
    && pip install --no-cache-dir --break-system-packages --use-deprecated=legacy-resolver -r requirements.txt \
    && huggingface-cli download opendatalab/PDF-Extract-Kit-1.0 --local-dir /app/models/mineru/pipeline \
    && huggingface-cli download opendatalab/MinerU2.5-2509-1.2B --local-dir /app/models/mineru/vlm \
    && python3 -c "import json; config = {'models-dir': {'pipeline': '/app/models/mineru/pipeline', 'vlm': '/app/models/mineru/vlm'}, 'config_version': '1.3.1'}; open('/app/mineru.json', 'w').write(json.dumps(config, indent=2))" \
    && python3 check_dependencies.py \
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
