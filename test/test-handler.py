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
import time

# Add the root directory to sys.path to import handler
sys.path.append("/")

# Mock the runpod module to avoid starting the serverless loop
import runpod
runpod.serverless = type('obj', (object,), {'start': lambda x: print("Mock runpod.serverless.start called")})

from handler import handler

def test_handler():
    """
    Simulates a RunPod job event and calls the handler.
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
            "marker_workers": 0,
            "marker_paginate_output": True,
            "marker_use_llm": True,
            "marker_force_ocr": False
        }
    }

    print(f"Job Payload: {json.dumps(job, indent=2)}")

    try:
        # Call the handler directly
        result = handler(job)

        print("\n--- Handler Result ---")
        print(json.dumps(result, indent=2))

        storage_bucket_path = os.environ.get('VOLUME_ROOT_MOUNT_PATH')

        input_path=f"{storage_bucket_path}/{input_dir}"

        if result.get("status") == "completed" \
                and result.get("message") == f"All input files of {input_path} processed.":
            print("\nSUCCESS: Handler completed successfully.")

        else:
            print("\nFAILURE: Handler returned non-completed status.")
            sys.exit(1)

    except Exception as e:
        print(f"\nFAILURE: Exception occurred during handler execution: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_handler()
