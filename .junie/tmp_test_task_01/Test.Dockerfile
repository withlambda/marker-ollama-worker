FROM pytorch/pytorch:2.10.0-cuda12.6-cudnn9-runtime

# Install system dependencies for OpenCV and other packages
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install PaddlePaddle GPU first as it requires a specific index
RUN pip install --no-cache-dir --break-system-packages \
    paddlepaddle-gpu==3.3.0 \
    -i https://www.paddlepaddle.org.cn/packages/stable/cu126/

# Install MinerU[full] and other critical packages
RUN pip install --no-cache-dir --break-system-packages \
    "mineru[full]==3.0.1" \
    "vllm==0.18.0" \
    "psutil==5.9.0" \
    "requests==2.31.0" \
    "runpod==1.8.1" \
    "httpx==0.28.1" \
    "huggingface_hub==0.36.2" \
    "pydantic==2.12.5" \
    "pydantic-settings==2.12.0" \
    "json-repair==0.58.7" \
    "transformers==4.57.6"

WORKDIR /test
