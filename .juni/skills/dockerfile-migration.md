# Skill: Dockerfile Migration — Ollama to vLLM

## Role
Responsible for updating the `Dockerfile` to replace Ollama installation with vLLM, ensuring the container image can run the vLLM server as a subprocess alongside the Marker OCR pipeline.

## Prerequisites
- `settings-migration.md` must be completed (defines the `VLLM_*` environment variables).
- Review the current `Dockerfile` to understand the existing Ollama installation steps before making changes.

## Scope
- Modify `Dockerfile`.
- Update any related build scripts (`release.sh`) if they reference Ollama.
- Update `config/` scripts if they handle Ollama model downloads.

## Task 1: Analyze Current Dockerfile
Before making changes, identify:
1. Which lines install Ollama (binary download, apt packages, etc.).
2. Which lines configure Ollama (env vars, model paths, startup scripts).
3. Which lines download or pre-load Ollama models.
4. Base image and CUDA version in use.

## Task 2: Remove Ollama Components
- Remove Ollama binary installation steps.
- Remove Ollama-specific environment variables (`OLLAMA_MODELS`, `OLLAMA_HOST`, `OLLAMA_LOG_DIR`, etc.).
- Remove any Ollama model download/build steps.
- Remove Ollama health check or startup scripts.

## Task 3: Add vLLM Installation
- Install vLLM via `pip install vllm` in the Dockerfile (vLLM runs as a server process inside the container).
- Ensure the CUDA version in the base image is compatible with vLLM's requirements.
- If vLLM requires a specific PyTorch version, pin it explicitly.
- **Note**: vLLM is installed in the Docker image (not in `requirements.txt`) because it runs as a standalone server, not as a library imported by the worker code.

## Task 4: Update Environment Variables
Replace Ollama env vars with vLLM defaults in the Dockerfile:

```dockerfile
# Remove these
ENV OLLAMA_MODELS=/path/to/models
ENV OLLAMA_HOST=http://127.0.0.1:11434

# Add these
ENV VLLM_MODEL_PATH=/path/to/model/weights
ENV VLLM_PORT=8000
ENV VLLM_GPU_UTIL=0.90
ENV VLLM_MAX_MODEL_LEN=16384
```

Only set defaults that are specific to the container environment. Runtime-configurable values should be left to the user via `docker run -e`.

## Task 5: Update Model Download Scripts
- Review `config/download-models` scripts.
- If they download Ollama-specific model formats, update them to download vLLM-compatible model weights (typically Hugging Face format).
- The model download scripts in `config/` may reference `models/huggingface/` — ensure this path is consistent with `VLLM_MODEL_PATH`.

## Task 6: Update `release.sh`
- Review `release.sh` for any Ollama-specific build or push steps.
- Update Docker image tags or labels if they reference Ollama.

## Task 7: Verify Container Build
- Ensure `docker build` completes without errors.
- Ensure the resulting image can:
  1. Start the worker process.
  2. Launch vLLM as a subprocess.
  3. Respond to a health check on the vLLM port.

## Considerations
- **Image size**: vLLM with CUDA dependencies can be large (~10+ GB). Consider multi-stage builds if the base image is already large.
- **CUDA compatibility**: vLLM requires specific CUDA versions. Verify the base image's CUDA version matches vLLM's requirements.
- **Model weights**: Model weights should be mounted as volumes, not baked into the image (consistent with current approach using `VOLUME_ROOT_MOUNT_PATH`).
