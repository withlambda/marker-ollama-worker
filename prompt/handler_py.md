# RunPod Handler (handler.py)

## Context
The main entry point for the RunPod Serverless worker. Orchestrates the two-phase conversion process: Marker-PDF (PDF -> Markdown) and vLLM post-processing (error correction and vision).

## Interface
### `handler(job: Dict[str, Any]) -> Dict[str, Any]`
- Input: Job containing `input` dictionary from RunPod.
- Output: Status dictionary with `status`, `message`, and `failures`.
- Job Statuses: `completed`, `partially_completed`, `success`.

## Logic
### Phase 1: Marker Conversion
- Parallel file processing via `multiprocessing.Pool` with `spawn` start method.
- Auto-tuning of worker count based on `VRAM_GB_TOTAL` and `VRAM_GB_PER_WORKER`.
- Worker process recycling (`maxtasksperchild`) to manage memory.

### Phase 2: vLLM Post-processing
- Sequential file processing with parallel internal chunk/image processing.
- Error-resilient transition: If the vLLM server or processing fails critically, the job returns `partially_completed` with existing results instead of crashing.
- Integrated vision support: Extract images, describe them via vLLM, and insert descriptions into the output file.

## Goal
Regenerate a production-grade RunPod handler that efficiently orchestrates multiple ML phases, implements VRAM-aware worker tuning, and provides a resilient API response schema that accounts for partial job successes.
