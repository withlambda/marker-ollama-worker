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

ARG PYTHON_VERSION
FROM python:${PYTHON_VERSION}-slim

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir huggingface_hub

WORKDIR /app

ENV HF_HOME=/app/cache/huggingface

RUN mkdir -p ${HF_HOME}

COPY download-models-from-hf.sh exec-model-download.sh functions.sh *.txt ./

CMD ["./download-models-from-hf.sh"]
