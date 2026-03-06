#!/bin/bash

# load functions
. functions.sh

process_list_file -c hf_download -f "${MODELS_FILE:?No models file specified.}"
