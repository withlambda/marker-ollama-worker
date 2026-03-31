# Task 01 — Dockerfile Overhaul

## Dependencies
- None (first task)

## Requirements Traced
- FR-2 (Docker Image with Baked-In Models)
- NFR-2 (Build Reproducibility)
- EC-1 (PaddlePaddle GPU Compatibility)
- EC-4 (Model Download During Build)

## Pinned Compatibility Baseline

- Base image: `pytorch/pytorch:2.10.0-cuda12.6-cudnn9-runtime`
- `mineru[full]==3.0.1`
- `paddlepaddle-gpu==3.3.0`
- `vllm==0.18.0`
- Paddle index URL: `https://www.paddlepaddle.org.cn/packages/stable/cu126/`
- MinerU model script source: `opendatalab/MinerU` tag `v3.0.1`

## Implementation Steps

### 0. Produce a Compatibility Proof (Mandatory Gate Before Editing)

> **Status Update**: User confirmed `paddlepaddle-gpu==3.3.0` supports CUDA 12.6 via the `cu126` index.

To avoid repeated multi-GB downloads during verification, perform the compatibility check using a temporary test Docker container:

1. **Create a temporary `Dockerfile.test`**:
   - Use `FROM pytorch/pytorch:2.10.0-cuda12.6-cudnn9-runtime`.
   - Install system dependencies: `apt-get update && apt-get install -y libgl1 libglib2.0-0 curl`.
   - Install `mineru[full]==3.0.1` and other required packages directly in the Dockerfile using:
     ```bash
     pip install --break-system-packages mineru[full]==3.0.1 paddlepaddle-gpu==3.3.0 vllm==0.18.0 --extra-index-url https://www.paddlepaddle.org.cn/packages/stable/cu126/
     ```
   - Fetch the `download_models_hf.py` script and bake the models into the image to ensure a network-independent test environment.

2. **Run the Test Container with a mounted shell script**:
   - Create a shell script `test_all.sh` containing all verification commands (PyTorch check, MinerU import, `vllm` import, `mineru.json` schema inspection, etc.).
   - Execute the test container by mounting the shell script and a results file:
     ```bash
     docker run --rm \
       -v $(pwd)/test_all.sh:/test_all.sh \
       -v $(pwd)/test_results.txt:/test_results.txt \
       notelm-mineru-test bash /test_all.sh
     ```
   - The `test_all.sh` script must append all command outputs and results to `/test_results.txt`.

3. **Verify the Proof Artifact**:
   - Evaluate `test_results.txt` after the container stops. This file serves as the mandatory gate.
   - Confirm that the `pytorch:2.10.0` image contains a working PyTorch installation.
   - Confirm that `mineru[full]==3.0.1`, `paddlepaddle-gpu==3.3.0`, and `vllm==0.18.0` can all be imported.
   - Inspect the real CLI/argument contract of the `download_models_hf.py` script.
   - Determine whether the downloader requires Hugging Face authentication or writes to hard-coded paths.
   - Verify the exact `mineru.json` schema expected by `mineru[full]==3.0.1`.

Do **not** bake production Dockerfile assumptions until this proof step is complete and verified.

### 1. Update `requirements.txt`
- Remove `marker-pdf==1.10.2`.
- Add `mineru[full]==3.0.1`.
- Pin `vllm==0.18.0` explicitly (verify compatibility with CUDA 12.6 base image during Step 0).
- **Note on PaddlePaddle**: `paddlepaddle-gpu==3.3.0` requires a non-PyPI index URL. Since `requirements.txt` does not natively support per-line `--extra-index-url`, choose one of:
  - Option A: Add `--extra-index-url https://www.paddlepaddle.org.cn/packages/stable/cu126/` as the first line of `requirements.txt` (pip supports this).
  - Option B: Keep `paddlepaddle-gpu==3.3.0` out of `requirements.txt` and install it via a separate `pip install` line in the Dockerfile.
- Remove any marker-specific transitive dependencies that are no longer needed (verify each one is not used by other packages like vLLM).

### 2. Update `Dockerfile`
- **Remove marker-specific build steps**:
  - Remove `python3 -c "from marker.util import assign_config, download_font; download_font();"`.
  - Remove the conditional `DOWNLOAD_MARKER_MODELS` block that runs `create_model_dict()`.
  - Remove `ARG DOWNLOAD_MARKER_MODELS="false"`.
- **Remove `tesseract-ocr`** from `apt-get install` (MinerU uses PaddleOCR, not Tesseract). Keep `poppler-utils` if needed for PDF utilities.
- **Add MinerU system dependencies**: Add `libgl1` and `libglib2.0-0` for OpenCV (required by MinerU/PaddlePaddle).
- **Install PaddlePaddle GPU**: Add a separate `pip install` line with the PaddlePaddle index URL if the wheel is not on PyPI.
- **Download MinerU models during build**:
  - Fetch the official `download_models_hf.py` script from the MinerU GitHub repository pinned to tag `v3.0.1`:
    ```dockerfile
    RUN curl -L -o /tmp/download_models_hf.py \
        https://raw.githubusercontent.com/opendatalab/MinerU/v3.0.1/scripts/download_models_hf.py
    ```
  - **Use only the CLI interface verified in Step 0**: Inspect the downloaded script to confirm it accepts `--models-dir` (or equivalent) as an argument. The actual argument name and behavior may differ from what is assumed here. If the script downloads to a hardcoded path or uses different flags, adapt the Dockerfile command accordingly.
  - Run the script to download models to a known directory (e.g., `/app/models/mineru`):
    ```dockerfile
    RUN python3 /tmp/download_models_hf.py --models-dir /app/models/mineru
    ```
  - If the script requires Hugging Face authentication, add `ARG HF_TOKEN` and set `HUGGING_FACE_HUB_TOKEN` only for the build step, based on the Step 0 proof.
- **Generate `mineru.json`**:
  - Create the configuration file during build pointing to the baked-in model directory:
    ```dockerfile
    RUN python3 -c "import json; config = {'models-dir': '/app/models/mineru', ...}; \
        open('/app/mineru.json', 'w').write(json.dumps(config, indent=2))"
    ```
  - Alternatively, use a `COPY` of a pre-written `mineru.json` template.
- **Set environment variable**:
  ```dockerfile
  ENV MINERU_TOOLS_CONFIG_PATH="/app/mineru.json"
  ```
- **Keep build fully non-interactive and fail-fast**:
  - Preserve `DEBIAN_FRONTEND=noninteractive` and use non-interactive package install flags.
  - Keep strict shell behavior (`set -e` equivalent in chained RUN blocks).
- **Prevent runtime model downloads**:
  - Ensure no startup path in the container triggers model downloads; all model artifacts must exist after image build.
- **Update `check_dependencies.py` invocation** — this file is updated in Task 04, but ensure the `COPY` and `RUN python3 check_dependencies.py` step still works after the dependency changes.

## Test Requirements
- The compatibility proof (Step 0) is recorded in `test_results.txt` via the temporary test container and matches the final implementation choices.
- The production Dockerfile must build successfully (`docker build -t notelm-mineru .`).
- `check_dependencies.py` must pass inside the built container (after Task 04 updates it).
- `python3 -c "import mineru; print(mineru.__version__)"` must succeed inside the container.
- `python3 -c "import paddle; print(paddle.__version__)"` must succeed inside the container.
- `python3 -c "import vllm; print(vllm.__version__)"` must succeed inside the container.
- The `mineru.json` file must exist at the configured path with correct model directory references.
- Model files must exist in `/app/models/mineru/` (or configured path) without requiring network access at runtime.
- A smoke-run with networking disabled must not attempt model downloads (fail only if model files are truly missing).
- Record the final Docker image size and compare it against the previous Marker-based image. If the new image exceeds the old one by more than 50%, document the reason and assess whether layer optimization is needed.
