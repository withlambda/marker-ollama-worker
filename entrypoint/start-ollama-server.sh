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

echo "Starting Ollama service..."
# Start Ollama in the background. It will use OLLAMA_MODELS env var.
# Redirect logs to prevent the background process from blocking the script output
gosu appuser ollama serve > ollama.log 2>&1 &
OLLAMA_PID=$!
echo "OLLAMA PID: ${OLLAMA_PID}"

# --- 3. Health Check ---

echo "Waiting for Ollama to start..."
MAX_RETRIES=30
RETRY_COUNT=0
until curl -s http://127.0.0.1:11434 > /dev/null; do
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "Error: Ollama failed to start after $MAX_RETRIES attempts."
        cat ollama.log
        exit 1
    fi
    echo "Waiting for Ollama... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done
echo "Ollama is up and running!"
