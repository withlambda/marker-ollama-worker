#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Check that required environment variables are available
source base-validation-and-config.sh

source start-ollama-server.sh
source build-ollama-model.sh

echo "here1"

source run-handler.sh
