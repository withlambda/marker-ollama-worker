#!/bin/bash

set -e

SCRIPT_DIR=$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)

# load functions
. "${SCRIPT_DIR}/functions.sh"

echo "${MODELS_FILES:?No model files specified.}" | tr ',' '\n' | while read -r file; do
  echo "Read file $file to obtain models to be downloaded."
  process_list_file -c hf_download -f "${file:?No model file specified.}"
done
