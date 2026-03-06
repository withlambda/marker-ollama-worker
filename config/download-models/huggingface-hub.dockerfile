ARG PYTHON_VERSION
FROM python:${PYTHON_VERSION}-slim

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir huggingface_hub

WORKDIR /app

ENV HF_HOME=/app/cache/huggingface

RUN mkdir -p ${HF_HOME}

COPY download-models-from-hf.sh exec-model-download.sh functions.sh *.txt ./

CMD ["./download-models-from-hf.sh"]
