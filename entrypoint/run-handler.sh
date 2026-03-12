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

# --- Run Handler ---

# Starts the Python handler script using gosu to run as the 'appuser'.
#
# Environment Variables:
#   HANDLER_FILE_NAME (string): The name of the python script to run (default: handler.py).
#
# Usage:
#   Runs 'python3 -u <HANDLER_FILE_NAME>' as 'appuser'.
#   '-u' ensures unbuffered output for immediate logging.

echo "Starting RunPod Handler..."
# Execute the Python handler script.

# -u ensures unbuffered output so logs appear immediately.

exec gosu appuser python3 -u "${HANDLER_FILE_NAME}"

# Note: The handler script calls runpod.serverless.start(), which blocks.
# If the handler exits, the container should exit.
