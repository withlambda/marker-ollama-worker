# Use a PyTorch base image optimized for RunPod
# This image includes CUDA 12.1.1, Python 3.10, and PyTorch 2.2.0
FROM runpod/pytorch:2.2.0-py3.10-cuda12.1.1-devel

# Set environment variables to avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies required for marker-pdf and general utility
# poppler-utils: Required for PDF processing
# tesseract-ocr: Required for OCR capabilities
# curl: Required for installing Ollama
# git: Required for installing marker-pdf from source if needed (though we use pip)
RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
# We use the official install script.
RUN curl -fsSL https://ollama.com/install.sh | sh

# Install marker-pdf
# Pinning to a specific version for reproducibility.
# Adjust the version as needed based on compatibility with PyTorch 2.2.0.
# As of late 2023/early 2024, marker-pdf is actively developed.
# We install via pip.
RUN pip install marker-pdf==0.2.10

# Copy the entrypoint script into the container
COPY entrypoint.sh /entrypoint.sh

# Make the entrypoint script executable
RUN chmod +x /entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["/entrypoint.sh"]
