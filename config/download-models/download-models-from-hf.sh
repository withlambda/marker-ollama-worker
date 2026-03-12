#!/bin/bash
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

set -e

# This script downloads machine learning models from Hugging Face based on lists provided in text files.
# It uses helper functions defined in 'functions.sh'.
#
# Environment Variables:
#   MODELS_FILES (string): A comma-separated list of file paths. Each file contains a list of Hugging Face model IDs.
#
# Usage:
#   ./download-models-from-hf.sh
#   (Requires MODELS_FILES to be set)

SCRIPT_DIR=$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)

# load functions
. "${SCRIPT_DIR}/functions.sh"

echo "${MODELS_FILES:?No model files specified.}" | tr ',' '\n' | while read -r file; do
  echo "Read file $file to obtain models to be downloaded."
  process_list_file -c hf_download -f "${file:?No model file specified.}"
done
