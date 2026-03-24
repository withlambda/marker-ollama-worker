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

import sys
import os
import json
from pathlib import Path

# Add the root directory to sys.path to import handler
# In Docker, test-handler.py might be in the same directory as handler.py
# Locally, it's usually in a test/ subdirectory.
current_dir = Path(__file__).resolve().parent
if (current_dir / "handler.py").exists():
    PROJECT_ROOT = current_dir
else:
    PROJECT_ROOT = current_dir.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# Mock the runpod module to avoid starting the serverless loop
import runpod
runpod.serverless = type('obj', (object,), {'start': lambda _: print("Mock runpod.serverless.start called")})

from handler import handler

def test_handler() -> None:
    """
    Simulates a RunPod job event and calls the handler.

    This function sets up a mock job payload, invokes the main handler logic,
    and prints the result. It effectively tests the end-to-end processing pipeline
    without needing a live RunPod environment.

    The function performs the following steps:
    1.  Defines a sample job payload mimicking the RunPod event structure.
    2.  Sets up input and output directories relative to the mocked storage path.
    3.  Calls the `handler` function directly with the payload.
    4.  Verifies the result status and message.
    5.  Exits with code 0 on success, or 1 on failure.
    """
    print("--- Starting Local Handler Test ---")

    input_dir="input"
    output_dir="output"

    # Define a sample job payload
    # This mimics the structure RunPod sends to the handler
    job = {
        "input": {
            "input_dir": input_dir, # Process the entire input directory
            "output_dir": output_dir,
            "marker_workers": 1,
            "vllm_chunk_workers": 1,
            "marker_paginate_output": True,
            "marker_force_ocr": False,
            "marker_disable_multiprocessing": True
        }
    }

    print(f"Job Payload: {json.dumps(job, indent=2)}")

    try:
        # Call the handler directly
        result = handler(job)

        print("\n--- Handler Result ---")
        print(json.dumps(result, indent=2))

        storage_bucket_path = Path(os.environ.get('VOLUME_ROOT_MOUNT_PATH', ""))

        input_path = storage_bucket_path / input_dir

        if result.get("status") == "completed" \
            and result.get("message") == f"All {sum(1 for _ in input_path.glob('*'))} input files of {input_path.absolute()} were processed successfully." \
            and result.get("failures") is None:
            print("\nSUCCESS: Handler completed successfully.")

        else:
            print("\nFAILURE: Handler returned non-completed status.")
            sys.exit(1)

    except Exception as e:
        print(f"\nFAILURE: Exception occurred during handler execution: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_handler()
