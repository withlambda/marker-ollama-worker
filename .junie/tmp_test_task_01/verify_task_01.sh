#!/bin/bash
set -e

RESULTS_FILE="/test/task_01_results.txt"
echo "--- TASK 01 VERIFICATION RESULTS ---" > "$RESULTS_FILE"
echo "Timestamp: $(date)" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

echo "Checking Versions..." >> "$RESULTS_FILE"
python3 -c "import torch; print(f'PyTorch version: {torch.__version__}')" >> "$RESULTS_FILE" 2>&1 || echo "ERROR: PyTorch import failed" >> "$RESULTS_FILE"
python3 -c "import mineru; print(f'MinerU version: {mineru.__version__}')" >> "$RESULTS_FILE" 2>&1 || echo "ERROR: MinerU import failed" >> "$RESULTS_FILE"
python3 -c "import paddle; print(f'PaddlePaddle version: {paddle.__version__}')" >> "$RESULTS_FILE" 2>&1 || echo "ERROR: PaddlePaddle import failed" >> "$RESULTS_FILE"
python3 -c "import vllm; print(f'vLLM version: {vllm.__version__}')" >> "$RESULTS_FILE" 2>&1 || echo "ERROR: vLLM import failed" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

echo "Checking MinerU Configuration Logic..." >> "$RESULTS_FILE"
cat <<EOF > check_mineru_config.py
import json
import os
import sys
from mineru.utils.config_reader import read_config

# Test 1: No config file or env var
print("Test 1 (No Config):")
config = read_config()
print(f"  Config read: {config is not None}")

# Test 2: MINERU_TOOLS_CONFIG_JSON env var
print("\nTest 2 (MINERU_TOOLS_CONFIG_JSON):")
test_config = {"models-dir": "/tmp/models"}
os.environ["MINERU_TOOLS_CONFIG_JSON"] = json.dumps(test_config)
config = read_config()
print(f"  Config models-dir: {config.get('models-dir') if config else 'None'}")
del os.environ["MINERU_TOOLS_CONFIG_JSON"]

# Test 3: Custom config file via env var
print("\nTest 3 (Custom config file):")
with open("/tmp/test_mineru.json", "w") as f:
    json.dump({"models-dir": "/tmp/custom_models"}, f)
os.environ["MINERU_TOOLS_CONFIG_PATH"] = "/tmp/test_mineru.json"
config = read_config()
print(f"  Config models-dir: {config.get('models-dir') if config else 'None'}")
EOF

python3 check_mineru_config.py >> "$RESULTS_FILE" 2>&1
echo "" >> "$RESULTS_FILE"

echo "Verifying presence of OpenCV system dependencies..." >> "$RESULTS_FILE"
python3 -c "import cv2; print(f'OpenCV version: {cv2.__version__}')" >> "$RESULTS_FILE" 2>&1 || echo "ERROR: OpenCV import failed" >> "$RESULTS_FILE"

echo "" >> "$RESULTS_FILE"
echo "--- VERIFICATION COMPLETE ---" >> "$RESULTS_FILE"
