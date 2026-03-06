ARG PYTHON_VERSION=3.11.12
FROM python:${PYTHON_VERSION}-slim

ENV HF_HOME=/app/cache/huggingface

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir huggingface_hub


WORKDIR /app

RUN mkdir -p ${HF_HOME}

COPY download-models-from-hf.sh exec-model-download.sh functions.sh marker-models.txt ./

CMD ["./download-models-from-hf.sh"]

