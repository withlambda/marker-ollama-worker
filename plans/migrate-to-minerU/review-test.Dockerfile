FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        git \
        curl \
        libgl1 \
        libglib2.0-0 \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install paddlepaddle==3.3.0 \
    && python -m pip install -r /tmp/requirements.txt \
    && python -m pip install \
        pytest \
        charset-normalizer==3.4.4 \
        pillow==11.1.0 \
        reportlab==4.3.1
