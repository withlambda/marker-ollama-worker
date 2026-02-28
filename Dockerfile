# 1. DEFINE BUILD ARGS BEFORE FROM
# This allows the variable to be used in the image name
ARG PYTORCH_VERSION=2.7.1
ARG CUDA_VERSION=12.8
ARG CUDNN_VERSION=9

# 2. BASE IMAGE
FROM pytorch/pytorch:${PYTORCH_VERSION}-cuda${CUDA_VERSION}-cudnn${CUDNN_VERSION}-runtime

# 3. DEFINE APP ARGS
# Args defined before FROM are lost after FROM, so we define app args here
ARG MARKER_VERSION=1.10.2
ARG RUNPOD_VERSION=1.8.1

# 4. ENVIRONMENT SETTINGS
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
	OLLAMA_HOST=0.0.0.0 \

# 5. SYSTEM DEPENDENCIES
# poppler-utils: Required for PDF processing
# tesseract-ocr: Required for OCR capabilities
# curl: Required for installing Ollama
# git: Required for installing marker-pdf from source if needed (though we use pip)
RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    curl \
    git \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 6. OLLAMA INSTALLATION
RUN curl -fsSL https://ollama.com/install.sh | sh

# 7. PYTHON DEPENDENCIES
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    psutil \
    marker-pdf==${MARKER_VERSION} \
    runpod==${RUNPOD_VERSION} && \
   	python3 -c "from marker.converters.pdf import PdfConverter; \
       from marker.models import create_model_dict; \
       PdfConverter(artifact_dict=create_model_dict())"

# 8. APPLICATION SETUP
WORKDIR /app
COPY handler.py ./entrypoint/ ./
RUN chmod +x entrypoint.sh

# 9. START COMMAND
CMD [ "./entrypoint.sh" ]
