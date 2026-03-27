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

"""
vLLM worker for document post-processing.
This module manages the lifecycle of a vLLM server subprocess, including
startup with health check polling, graceful shutdown, and OpenAI-compatible
API communication for OCR error correction and image description generation.
"""

import asyncio
import base64
import json
import os
import logging
import random
import signal
import subprocess
import threading
import time
from json_repair import repair_json
from pathlib import Path
from typing import Optional, List, Tuple, Callable, Coroutine, Any, TypeVar

import httpx
import openai
import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from openai.types.chat import (
    ChatCompletionUserMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionContentPartImageParam, ChatCompletionContentPartTextParam
)
from openai.types.chat.chat_completion_content_part_image_param import ImageURL

from settings import VllmSettings
from utils import ImageTokenCalculator

# Configure logging
logger = logging.getLogger(__name__)

_T = TypeVar("_T")


class VllmWorker:
    """
    Manages the vLLM server lifecycle and handles LLM text processing tasks.

    This class provides methods to:
    - Start and stop the vLLM server as a subprocess.
    - Poll the health endpoint until the server is ready.
    - Process text chunks in parallel using the OpenAI-compatible vLLM API.
    - Describe images via the vision-language model endpoint.
    - Handle server crashes with one automatic restart attempt.

    The vLLM server is started on-demand and communicates via an
    OpenAI-compatible REST API using the ``openai`` Python client.
    """

    def __init__(self, settings: VllmSettings) -> None:
        """
        Initialize the VllmWorker.

        Args:
            settings: Validated vLLM configuration (model path, VRAM, ports, etc.).
        """
        self.settings = settings
        self.process: Optional[subprocess.Popen] = None
        self._client: Optional[openai.AsyncOpenAI] = None
        self._restart_attempted: bool = False

        self.image_token_calculator = ImageTokenCalculator(
            model_path=self.settings.vllm_model_path,
            model_name=self.settings.vllm_model
        )

        logger.info(
            f"VllmWorker initialized with model={self.settings.vllm_model}, "
            f"host={self.settings.vllm_host}, port={self.settings.vllm_port}"
        )

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "VllmWorker":
        """
        Context manager entry: starts the vLLM server, waits for readiness,
        and initializes the OpenAI client.
        """
        try:
            self.start_server()
        except Exception:
            self.stop_server()
            raise
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit: gracefully shuts down the vLLM server."""
        self.stop_server()

    def __del__(self) -> None:
        """Ensure the server subprocess is stopped on garbage collection."""
        self.stop_server()

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------

    def start_server(self, vram_recovery_delay: Optional[int] = None) -> None:
        """
        Launch the vLLM server as a subprocess and wait for it to become ready.

        1. Wait for ``vllm_vram_recovery_delay`` seconds (VRAM recovery phase).
        2. Spawn ``vllm serve`` with CLI arguments derived from ``VllmSettings``.
        3. Poll ``GET /health`` until HTTP 200 or ``vllm_startup_timeout`` elapses.
        4. Initialize the ``openai.AsyncOpenAI`` client.

        Args:
            vram_recovery_delay: Override for the VRAM recovery delay.  If *None*,
                uses ``self.settings.vllm_vram_recovery_delay``.

        Raises:
            RuntimeError: If the server fails to start or the health check times out.
        """
        # If already running, nothing to do
        if self.process is not None and self.process.poll() is None:
            logger.info("vLLM server is already running.")
            return

        # Clean up any dead process handle
        if self.process is not None:
            logger.warning("vLLM server process was found dead. Cleaning up before restart.")
            self._cleanup_process()

        # --- VRAM Recovery Phase ---
        delay = vram_recovery_delay if vram_recovery_delay is not None else self.settings.vllm_vram_recovery_delay
        if delay > 0:
            logger.info(f"Waiting {delay}s for GPU VRAM recovery before starting vLLM...")
            time.sleep(delay)

        # --- Build CLI command ---
        cmd = self._build_serve_command()
        logger.info(f"Starting vLLM server: {' '.join(cmd)}")

        # --- Launch subprocess ---
        env = os.environ.copy()

        # Forces fresh CUDA initialization in the child
        env["VLLM_WORKER_MULTIPROC_METHOD"] = "spawn"
        # Critical if Marker used the GPU earlier
        env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

        if self.settings.vllm_cpu:
            env["VLLM_TARGET_DEVICE"] = "cpu"

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            start_new_session=True,
        )
        logger.info(f"vLLM subprocess started (PID {self.process.pid})")

        # --- Health-check polling ---
        self._wait_for_ready()

        # --- Create OpenAI client ---
        self._client = openai.AsyncOpenAI(
            base_url=f"http://localhost:{self.settings.vllm_port}/v1",
            api_key="EMPTY",  # vLLM does not require a real API key
        )

        logger.info("vLLM server is ready and OpenAI client initialized.")

    def stop_server(self) -> None:
        """
        Gracefully shut down the vLLM server subprocess.

        Sends SIGTERM, waits up to ``vllm_shutdown_grace_period`` seconds,
        then sends SIGKILL if the process is still running.
        """
        if self.process is None:
            return

        pid = self.process.pid
        shutdown_grace_period = self.settings.vllm_shutdown_grace_period
        logger.info(f"Stopping vLLM server (PID {pid})...")

        try:
            # Send SIGTERM for graceful shutdown
            self.process.send_signal(signal.SIGTERM)
            try:
                self.process.wait(timeout=shutdown_grace_period)
                logger.info(f"vLLM server (PID {pid}) terminated gracefully.")
            except subprocess.TimeoutExpired:
                logger.warning(
                    f"vLLM server (PID {pid}) did not exit within {shutdown_grace_period}s. "
                    f"Sending SIGKILL..."
                )
                self.process.kill()
                self.process.wait(timeout=5)
                logger.info(f"vLLM server (PID {pid}) killed.")
        except ProcessLookupError:
            logger.info(f"vLLM server (PID {pid}) already exited.")
        except Exception as e:
            logger.error(f"Error stopping vLLM server (PID {pid}): {e}")
        finally:
            self._cleanup_process()

    # ------------------------------------------------------------------
    # Text processing
    # ------------------------------------------------------------------

    @staticmethod
    def _run_async_from_sync(coroutine_factory: Callable[[], Coroutine[Any, Any, _T]]) -> _T:
        """
        Execute an async coroutine from a synchronous method.

        If the current thread has no running event loop, the coroutine is executed
        directly via ``asyncio.run``.

        If a loop is already running in the current thread (for example, when this
        worker is called from async application code), execution is delegated to a
        temporary background thread that owns its own event loop.

        Args:
            coroutine_factory: A zero-argument callable that returns the coroutine
                to execute.

        Returns:
            The coroutine result.

        Raises:
            RuntimeError: If background execution ends without a result.
            Exception: Re-raises any exception from the coroutine.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coroutine_factory())

        result_holder: List[_T] = []
        error_holder: List[Exception] = []

        def _runner() -> None:
            """Run the coroutine in a dedicated event loop hosted by this thread."""
            try:
                result_holder.append(asyncio.run(coroutine_factory()))
            except Exception as e:
                error_holder.append(e)

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join()

        if error_holder:
            raise error_holder[0]

        if not result_holder:
            raise RuntimeError("Async execution thread finished without producing a result.")

        return result_holder[0]

    def process_text(
        self,
        text: str,
        prompt_template: str,
        max_chunk_workers: int,
    ) -> str:
        """
        Post-process text using the vLLM model for OCR error correction.

        Chunks the text to stay within the context window and processes chunks
        concurrently using ``asyncio``.

        If *prompt_template* is ``None`` or empty, the OCR correction is skipped
        entirely, and the original text is returned unchanged (a warning is logged).

        Args:
            text: The full document text to process.
            prompt_template: System prompt for correction.  When ``None`` or
                 empty, the correction phase is skipped.
            max_chunk_workers: Maximum number of concurrent async tasks.

        Returns:
            The corrected text with all chunks rejoined, or the original text
            if no prompt is configured.

        Raises:
            ValueError: If the model name is not configured.
        """

        # Add the chunk formatting instruction to the prompt
        # add the beginning and end of the text to the prompt
        # to make sure the llm really uses the appropriate formatting
        # and does not forget about it.
        prompt_template = f"""
        {self.settings.vllm_chunk_output_formatting_instruction}

        {prompt_template}

        {self.settings.vllm_chunk_output_formatting_instruction}
        """

        # Note r is ~ 1.3 since the JSON output yields ~30 % overhead to the pure text output.
        effective_chunk_size: int = self._compute_effective_chunk_size(prompt_template, r=1.3)
        if effective_chunk_size <= 0:
            logger.error(
                "Skipping OCR error correction: prompt token usage leaves no room "
                "for chunk input/completion (max_model_len=%s). Returning original text.",
                self.settings.vllm_max_model_len,
            )
            return text

        chunks = self._chunk_text(text, effective_chunk_size)

        max_workers = max(1, int(max_chunk_workers))
        logger.info(f"Processing {len(chunks)} chunks with vLLM using {max_workers} async workers...")

        corrected_chunks = self._run_async_from_sync(
            lambda: self._process_chunks_async(chunks, prompt_template, max_workers)
        )

        return "\n\n".join(corrected_chunks)

    def process_file(
        self,
        file_path: Path,
        prompt_template: str,
        max_chunk_workers: int,
    ) -> bool:
        """
        Process a single file with the vLLM model.

        Reads the file, applies OCR error correction via :meth:`process_text`,
        and overwrites the file with the corrected content.

        Args:
            file_path: Path to the file to process.
            prompt_template: Custom system prompt.
            max_chunk_workers: Maximum number of concurrent async tasks.

        Returns:
            True if processing succeeded, False otherwise.
        """
        if not file_path.exists():
            return False

        logger.info(f"LLM Processing: {file_path.name}")
        try:
            original_text = file_path.read_text(encoding="utf-8")
            processed_text = self.process_text(
                text=original_text,
                prompt_template=prompt_template,
                max_chunk_workers=max_chunk_workers,
            )
            file_path.write_text(processed_text, encoding="utf-8")
            logger.info(f"Finished LLM processing for {file_path.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to post-process {file_path.name}: {e}")
            return False

    # ------------------------------------------------------------------
    # Image description
    # ------------------------------------------------------------------

    def describe_images(
        self,
        image_paths: List[Path],
        prompt_template: Optional[str],
        max_image_workers: int,
        target_language: Optional[str] = None,
    ) -> List[Tuple[Path, str]]:
        """
        Generate descriptions for multiple images via the vision-language model.

        Args:
            image_paths: Paths of images to describe.
            prompt_template: Optional custom system prompt for image description.
            max_image_workers: Maximum number of concurrent async tasks.
            target_language: Optional target language name for descriptions (e.g., "German").

        Returns:
            List of (image_path, description) tuples for described images,
            including placeholders for failures, preserving the original order.
        """
        if not image_paths:
            return []

        max_workers = max(1, int(max_image_workers))
        logger.info(f"Describing {len(image_paths)} extracted images with {max_workers} async worker(s)...")

        descriptions: List[Optional[str]] = self._run_async_from_sync(
            lambda: self._describe_images_async(image_paths, prompt_template, max_workers, target_language)
        )

        return [
            (image_path, description)
            for image_path, description in zip(image_paths, descriptions)
            if description is not None
        ]

    # ------------------------------------------------------------------
    # Internal helpers — async processing
    # ------------------------------------------------------------------

    async def _process_chunks_async(
        self,
        chunks: List[str],
        system_prompt: str,
        max_workers: int,
    ) -> List[str]:
        """
        Process all text chunks concurrently, bounded by *max_workers*.

        Logs summary statistics (total, succeeded, failed) after all chunks
        have been processed.

        Args:
            chunks: List of text chunks.
            system_prompt: The system prompt for OCR correction.
            max_workers: Semaphore limit for concurrent API calls.

        Returns:
            List of corrected chunks in original order.
        """
        semaphore = asyncio.Semaphore(max_workers)
        total = len(chunks)
        succeeded = 0
        failed = 0

        async def _bounded_process(index: int, chunk: str) -> Tuple[int, str]:
            """
            Process a single chunk with semaphore-based concurrency control.

            Args:
                index: Original index of the chunk.
                chunk: The text content of the chunk.

            Returns:
                Tuple containing the original index and the processed text.
            """
            async with semaphore:
                corrected_chunk = await self._process_single_chunk_async(chunk, system_prompt, index)
                return index, corrected_chunk

        tasks = [_bounded_process(index, chunk) for index, chunk in enumerate(chunks)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        corrected: List[str] = list(chunks)  # fallback copy
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Async chunk task failed: {result}")
                failed += 1
                continue
            idx, text = result
            # If the returned text is the same as the original chunk,
            # it was a fallback — count as failed
            if text is chunks[idx]:
                failed += 1
            else:
                succeeded += 1
            corrected[idx] = text

        logger.info(
            f"Chunk processing complete: {total} total, "
            f"{succeeded} succeeded, {failed} failed"
        )
        return corrected

    async def _process_single_chunk_async(
        self,
        chunk: str,
        system_prompt: str,
        chunk_index: int,
    ) -> str:
        """
        Process a single text chunk via the OpenAI chat completions API with retry logic.

        On retryable errors (connection, timeout, overloaded, server crash), the method
        backs off exponentially.  If the vLLM subprocess has died, one restart is
        attempted before giving up.

        Args:
            chunk: The text chunk to correct.
            system_prompt: System prompt for the model.
            chunk_index: Index of this chunk (for logging).

        Returns:
            The corrected text, or the original chunk as fallback on failure.
        """

        user_prompt: str = f"{self.settings.vllm_chunk_user_prompt_init}{chunk}"

        max_completion_tokens = self._compute_max_completion_tokens(
            self._count_tokens(system_prompt, user_prompt)
        )
        if max_completion_tokens <= 0:
            logger.error(
                "Skipping chunk %s: prompt token usage exceeds context window "
                "(max_model_len=%s). Returning original chunk.",
                chunk_index,
                self.settings.vllm_max_model_len,
            )
            return chunk

        for attempt in range(self.settings.vllm_max_retries + 1):
            try:
                response = await self._client.chat.completions.create(
                    model=self.settings.vllm_model,
                    messages=[
                        ChatCompletionSystemMessageParam(role="system", content=system_prompt),
                        ChatCompletionUserMessageParam(role="user", content=user_prompt),
                    ],
                    max_tokens=max_completion_tokens,
                    # 1. Force temperature to 0 for deterministic OCR correction
                    temperature=self.settings.vllm_temperature_text_chunk_correction,
                    # 2. This is the vLLM "magic" that prevents chatter
                    extra_body={
                        "guided_json": self.settings.vllm_output_json_schema
                    }
                )

                content = self.extract_ocr_text(response.choices[0].message.content)

                return content if content else chunk

            except Exception as e:
                is_last = attempt == self.settings.vllm_max_retries
                if self._is_retryable_error(e) and not is_last:
                    delay = self._compute_backoff(attempt, e)
                    logger.warning(
                        f"Retryable error on chunk {chunk_index} "
                        f"(attempt {attempt + 1}/{self.settings.vllm_max_retries + 1}). "
                        f"Retrying in {delay:.2f}s... Error: {e}"
                    )
                    # Check if the vLLM subprocess crashed and attempt one restart
                    await self._maybe_restart_server()
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(
                        f"Fatal error processing chunk {chunk_index} after {attempt + 1} attempts "
                        f"({len(chunk)} chunk size, {len(system_prompt)} prompt size, {max_completion_tokens} "
                        f"max completion_tokens, {len(chunk)+len(system_prompt)+max_completion_tokens} sum, "
                        f"{self.settings.vllm_max_model_len} allowed total): {e}"
                    )
                    return chunk  # fallback to the original

        logger.warning(f"Chunk {chunk_index} processing loop exited unexpectedly. Returning original.")
        return chunk

    def _compute_max_completion_tokens(
        self,
        *token_counts: int,
        upper_token_limit: Optional[int] = None,
    ) -> int:
        """Compute a safe completion budget so prompt + output fits model context."""
        available_tokens = (
            self.settings.vllm_max_model_len
            - sum(token_counts)
            - self.settings.vllm_chat_completion_token_safety_margin
        )
        if available_tokens <= 0:
            return 0
        return min(
            upper_token_limit or self.settings.vllm_max_model_len,
            available_tokens
        )

    def _compute_effective_chunk_size(self, system_prompt: str, r: float) -> int:
        """Compute a prompt-aware chunk-size budget using an output-to-input token ratio r."""
        if r < 0:
            raise ValueError("Output-to-input token ratio 'r' must be non-negative.")

        system_prompt_tokens = self._count_tokens(system_prompt)
        user_prompt_introduction = self._count_tokens(self.settings.vllm_chunk_user_prompt_init)
        context_budget = (
            self.settings.vllm_max_model_len
            - system_prompt_tokens
            - user_prompt_introduction
            - self.settings.vllm_chat_completion_token_safety_margin
        )
        if context_budget <= 0:
            return 0

        max_chunk_tokens_from_context = int(context_budget / (1.0 + r))
        if max_chunk_tokens_from_context <= 0:
            return 0
        return min(self.settings.vllm_chunk_size, max_chunk_tokens_from_context)

    async def _describe_images_async(
        self,
        image_paths: List[Path],
        prompt_template: Optional[str],
        max_workers: int,
        target_language: Optional[str] = None,
    ) -> List[Optional[str]]:
        """
        Describe all images concurrently, bounded by *max_workers*.

        Logs summary statistics (total, succeeded, failed) after all images
        have been processed.

        Args:
            image_paths: Paths of images to describe.
            prompt_template: Optional system prompt override.
            max_workers: Semaphore limit for concurrent API calls.
            target_language: Optional target language name for descriptions.

        Returns:
            List of description strings (including placeholders for failures) in original order.
        """
        semaphore = asyncio.Semaphore(max_workers)
        total = len(image_paths)
        succeeded = 0
        failed = 0

        async def _bounded_describe(index: int, path: Path) -> Tuple[int, Optional[str]]:
            """
            Describe a single image with semaphore-based concurrency control.

            Args:
                index: Original index of the image.
                path: File path to the image.

            Returns:
                Tuple containing the original index and the generated description.
            """
            async with semaphore:
                result_image_description = await self._describe_single_image_async(
                    path, prompt_template, index, target_language
                )
                return index, result_image_description

        tasks = [_bounded_describe(i, p) for i, p in enumerate(image_paths)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        descriptions: List[Optional[str]] = [None] * len(image_paths)
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Async image description task failed: {result}")
                failed += 1
                continue
            idx, desc = result
            if desc is None or "[Description unavailable]" in desc:
                failed += 1
            else:
                succeeded += 1
            descriptions[idx] = desc

        logger.info(
            f"Image description complete: {total} total, "
            f"{succeeded} succeeded, {failed} failed"
        )
        return descriptions

    async def _describe_single_image_async(
        self,
        image_path: Path,
        prompt_template: Optional[str],
        image_index: int,
        target_language: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generate a description for a single image using the vision-language model.

        The image is base64-encoded and sent as part of a multi-modal chat completion
        request via the OpenAI client with exponential backoff retry logic.

        Args:
            image_path: Path to the image file.
            prompt_template: Optional custom system instruction for the description.
                             If provided, it replaces the default system prompt.
            image_index: Zero-based image index for logging.
            target_language: Optional target language name for the description.

        Returns:
            The description string or a placeholder string on failure.
        """
        if not self.settings.vllm_model:
            raise ValueError("vllm_model not set for image description")

        system_prompt = prompt_template if prompt_template else \
            """
            You are an expert visual analyst. Provide a comprehensive, high-fidelity description of the provided image.

            Your analysis must cover the following categories in depth:
            1. Overall Scene: The setting, atmosphere, lighting, and artistic style (e.g., photorealistic,
                digital art, candid).
            2. Objects & Colors: Specific identification of all key objects, their materials, textures, and
                precise colors/shades.
            3. Human Subjects: (If present) Appearance, clothing, posture, perceived emotions, and actions.
            4. Textual Content: Verbatim transcription of any visible text or symbols.
            5. Spatial Relationships: The layout of the scene (foreground, midground, background) and how
                objects/persons are positioned relative to one another.
            6. Composition & Perspective: Camera angle (e.g., low-angle, birds-eye), depth of field, and framing.

            Structure: Return your analysis ONLY as a valid JSON object with a 'text' key.
            Constraint: Output the JSON string alone. No introductory text, no markdown code blocks, and no conversational filler.
            """

        if target_language:
            system_prompt = f"{system_prompt.rstrip()}\nLanguage: You must answer in {target_language}."

        system_prompt = f"""
        {self.settings.vllm_image_description_output_formatting_instruction}

        {system_prompt}

        {self.settings.vllm_image_description_output_formatting_instruction}
        """


        # Keep request-level user instruction short; avoid repeating template text
        # when it is already provided as the system prompt.
        user_instruction = "### IMAGE TO DESCRIBE\n"

        fallback_msg = "> **Image Description:** [Description unavailable]"

        prompt_tokens = self._count_tokens(system_prompt, user_instruction)

        image_tokens = self.image_token_calculator.calculate_image_tokens(image_source=image_path)

        max_completion_tokens = self._compute_max_completion_tokens(
            prompt_tokens, image_tokens,
            upper_token_limit=self.settings.vllm_image_description_max_tokens,
        )

        if max_completion_tokens < self.settings.vllm_min_completion_tokens:
            logger.warning(
                "Skipping image %s description: prompt token usage leaves no room "
                "for completion (max_model_len=%s, image_tokens=%s, prompt_tokens=%s). "
                "Returning fallback.",
                image_path.name,
                self.settings.vllm_max_model_len,
                image_tokens,
                prompt_tokens,
            )
            return fallback_msg

        try:
            # Read and base64-encode the image
            image_data = image_path.read_bytes()
            b64_image = base64.b64encode(image_data).decode("utf-8")

            # Determine MIME type from suffix
            suffix = image_path.suffix.lower()
            mime_map = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".bmp": "image/bmp",
                ".tif": "image/tiff",
                ".tiff": "image/tiff",
            }
            mime_type = mime_map.get(suffix, "image/png")
        except Exception as e:
            logger.error(f"Failed to prepare image {image_path.name} for description: {e}")
            return fallback_msg

        for attempt in range(self.settings.vllm_max_retries + 1):
            try:
                response = await self._client.chat.completions.create(
                    model=self.settings.vllm_model,
                    messages=[
                        ChatCompletionSystemMessageParam(role="system", content=system_prompt),
                        ChatCompletionUserMessageParam(
                            role="user",
                            content=[
                                ChatCompletionContentPartImageParam(
                                    type="image_url",
                                    image_url=ImageURL(url=f"data:{mime_type};base64,{b64_image}"),
                                ),
                                ChatCompletionContentPartTextParam(
                                    type="text",
                                    text=user_instruction
                                )
                            ]
                        ),
                    ],
                    max_tokens=max_completion_tokens,
                    temperature=self.settings.vllm_temperature_image_description,
                    # 2. This is the vLLM "magic" that prevents chatter
                    extra_body={
                        "guided_json": self.settings.vllm_output_json_schema
                    }
                )

                content = self.extract_ocr_text(response.choices[0].message.content)

                if not content:
                    logger.warning(f"Empty image description returned for {image_path.name}")
                    return fallback_msg
                return content

            except Exception as e:
                is_last = attempt == self.settings.vllm_max_retries
                if self._is_retryable_error(e) and not is_last:
                    delay = self._compute_backoff(attempt, e)
                    logger.warning(
                        f"Retryable error describing image {image_index + 1} "
                        f"(attempt {attempt + 1}/{self.settings.vllm_max_retries + 1}). "
                        f"Retrying in {delay:.2f}s... Error: {e}"
                    )
                    await self._maybe_restart_server()
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(
                        f"Fatal error describing image {image_index + 1} ({image_path.name}) "
                        f"after {attempt + 1} attempts: {e}"
                    )
                    return fallback_msg

        return fallback_msg

    # ------------------------------------------------------------------
    # Internal helpers — server management
    # ------------------------------------------------------------------

    def _build_serve_command(self) -> List[str]:
        """
        Build the CLI command list for launching ``vllm serve``.

        Returns:
            List of command-line tokens.
        """
        cmd = [
            "vllm", "serve",
            str(self.settings.vllm_model_path or self.settings.vllm_model),
            "--port", str(self.settings.vllm_port),
        ]

        if self.settings.vllm_cpu:
            cmd.extend(["--device", "cpu"])
        else:
            cmd.extend(["--gpu-memory-utilization", str(self.settings.vllm_gpu_util)])

        cmd.extend([
            "--max-model-len", str(self.settings.vllm_max_model_len),
            "--max-num-seqs", str(self.settings.vllm_max_num_seqs),
        ])

        # If the model name differs from the path, pass --served-model-name
        if self.settings.vllm_model_path:
            cmd.extend(["--served-model-name", self.settings.vllm_model])

        return cmd

    def _wait_for_ready(self) -> None:
        """
        Poll the vLLM health endpoint until the server is ready.

        Retries every ``vllm_health_check_interval`` seconds until either HTTP 200
        is received or ``vllm_startup_timeout`` elapses.

        If the health check fails or times out, the subprocess's stdout/stderr
        is captured and included in the raised ``RuntimeError`` for diagnostics.

        Raises:
            RuntimeError: If the health check times out or the subprocess exits
                prematurely.
        """
        health_url = f"http://localhost:{self.settings.vllm_port}/health"
        deadline = time.time() + self.settings.vllm_startup_timeout
        poll_interval = self.settings.vllm_health_check_interval

        logger.info(
            f"Polling vLLM health endpoint ({health_url}) "
            f"with timeout={self.settings.vllm_startup_timeout}s..."
        )

        while time.time() < deadline:
            # Check if the subprocess has exited
            if self.process is not None and self.process.poll() is not None:
                return_code = self.process.returncode
                output = ""
                try:
                    # Capture any remaining output without blocking
                    stdout, _ = self.process.communicate(timeout=2.0)
                    output = stdout if stdout else ""
                except subprocess.TimeoutExpired:
                    logger.debug(
                        "Timed out while capturing vLLM server output after premature exit; "
                        "proceeding without additional output."
                    )
                except Exception as exc:
                    logger.debug(
                        "Unexpected error while capturing vLLM server output after premature exit: %s",
                        exc,
                    )
                self._cleanup_process()
                raise RuntimeError(
                    f"vLLM server exited prematurely (exit code: {return_code}). Output:\n{output}"
                )

            try:
                with httpx.Client(timeout=5.0) as client:
                    resp = client.get(health_url)
                    if resp.status_code == 200:
                        logger.info("vLLM health check passed.")
                        return
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.TimeoutException):
                pass  # Server is not ready yet

            time.sleep(poll_interval)

        # Timeout reached — collect subprocess output and terminate
        output = ""
        if self.process is not None:
            try:
                # Capture output without blocking
                stdout, _ = self.process.communicate(timeout=2.0)
                output = stdout if stdout else ""
            except subprocess.TimeoutExpired:
                logger.debug(
                    "Timed out while capturing vLLM server output after startup timeout; "
                    "proceeding without additional output."
                )
            except Exception as exc:
                logger.debug(
                    "Unexpected error while capturing vLLM server output after startup timeout: %s",
                    exc,
                )
        self.stop_server()
        raise RuntimeError(
            f"vLLM health check timed out after {self.settings.vllm_startup_timeout}s. Output:\n{output}"
        )

    async def _maybe_restart_server(self) -> None:
        """
        Check if the vLLM subprocess has died and attempt one restart.

        This is called from within retry loops to recover from mid-processing
        crashes. Only one restart is attempted per worker lifetime to avoid
        infinite restart loops.
        """
        if self.process is None or self.process.poll() is None:
            return  # Still running or never started

        if self._restart_attempted:
            logger.error("vLLM server died and a restart was already attempted. Not retrying.")
            return

        self._restart_attempted = True
        logger.warning(
            f"vLLM server process (PID {self.process.pid}) died unexpectedly. "
            f"Attempting one restart..."
        )

        try:
            self._cleanup_process()
            # Use a shorter VRAM recovery delay for restarts
            self.start_server(vram_recovery_delay=2)
            logger.info("vLLM server restarted successfully.")
        except Exception as e:
            logger.error(f"Failed to restart vLLM server: {e}")

    def _cleanup_process(self) -> None:
        """
        Clean up the subprocess handle and close the stdout pipe.
        """
        if self.process is not None:
            try:
                if self.process.stdout:
                    self.process.stdout.close()
            except Exception as e:
                # Best-effort cleanup: failure to close stdout should not
                # prevent process cleanup, but we log it for debugging.
                logger.debug("Failed to close vLLM server stdout during cleanup: %s", e)
            self.process = None

    # ------------------------------------------------------------------
    # Internal helpers — retry logic
    # ------------------------------------------------------------------

    @staticmethod
    def _is_retryable_error(error: Exception) -> bool:
        """
        Determine whether an API error is transient and worth retrying.

        Args:
            error: The exception raised during an API call.

        Returns:
            True if the error is considered retryable.
        """
        error_msg = str(error).lower()
        retryable_patterns = [
            "connection refused",
            "connection error",
            "try again",
            "overloaded",
            "timeout",
            "503",
            "504",
            "server disconnected",
            "service unavailable",
        ]
        return any(pattern in error_msg for pattern in retryable_patterns)

    def _compute_backoff(self, attempt: int, error: Exception) -> float:
        """
        Compute the backoff delay for a given retry attempt.

        Uses exponential backoff with jitter. Severe errors (connection refused,
        server disconnected) use a 3× base delay.

        Args:
            attempt: Zero-based retry attempt number.
            error: The exception that triggered the retry.

        Returns:
            Delay in seconds before the next retry.
        """
        error_msg = str(error).lower()
        is_severe = "connection refused" in error_msg or "server disconnected" in error_msg
        base_delay = (self.settings.vllm_retry_delay * 3) if is_severe else self.settings.vllm_retry_delay
        return (base_delay * (2 ** attempt)) + (random.random() * self.settings.vllm_retry_delay)

    # ------------------------------------------------------------------
    # Internal helpers — Markdown-aware text chunking
    # ------------------------------------------------------------------


    def _count_tokens(self, *texts: str) -> int:
        """
        Count the total number of tokens in the provided text inputs.

        Uses the tiktoken encoding configured in ``vllm_tiktoken_encoding_name``.

        Args:
            *texts: One or more strings whose tokens need to be counted.

        Returns:
            The total number of tokens across all provided texts.
        """
        encoding = tiktoken.get_encoding(self.settings.vllm_tiktoken_encoding_name)
        return sum(
            len(encoding.encode(text, disallowed_special=())) for text in texts
        )

    def _chunk_text(self, text: str, chunk_size: int) -> List[str]:
        """
        Split Markdown text into chunks of approximately *chunk_size* tokens,
        preserving the Markdown structure.

        The method avoids splitting in the middle of:
        - Headings (lines starting with ``#``)
        - Fenced code blocks (delimited by triple backticks)
        - Tables (consecutive lines starting with ``|``)

        Token count is measured via tiktoken.

        Args:
            text: The Markdown text to split.
            chunk_size: Maximum *tokens* per chunk.

        Returns:
            List of text chunks.
        """

        # Split text into logical blocks separated by blank lines
        blocks = self._split_into_blocks(text)

        # Create a splitter that measures size in tokens
        splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name=self.settings.vllm_tiktoken_encoding_name,
            # Maximum number of tokens per chunk
            chunk_size=chunk_size,
            # Number of overlapping tokens
            chunk_overlap=0,
            # Keeps the separator at the end of the previous chunk,
            # required to keep the sentence dot at the end of a chunk.
            keep_separator="end",
            # It tries to split by paragraphs, then lines, then words
            separators=["\n\n", "\n", ".", " ", ""]
        )


        chunks: List[str] = []

        for block in blocks:

            chunks.extend([chunk for chunk in splitter.split_text(block) if chunk.strip()])

        return chunks

    @staticmethod
    def extract_ocr_text(raw_response: str) -> str:
        """
        Extracts OCR text from a raw JSON response.

        This method processes a string input assumed to be a JSON response containing OCR-extracted text.
        In the event of malformed or truncated JSON input, an attempt is made to repair the JSON before extracting
        the required text.

        :param raw_response: The raw JSON string containing OCR-extracted data.
        :return: The extracted OCR text as a string. If extraction is unsuccessful, an empty string is returned.
        """
        # 1. Attempt standard parsing
        try:
            data = json.loads(raw_response)
            return data.get("text", "")
        except (json.JSONDecodeError, TypeError):
            try:
                # 2. Attempt "Repairing" the truncated JSON
                repaired = repair_json(raw_response)
                data = json.loads(repaired)

                # We ensure data is a dict before calling .get()
                if isinstance(data, dict):
                    content = data.get("text", "")
                    if content:
                        logger.warning("OCR response was truncated and repaired. Text may be incomplete.")
                    return content
            except Exception as e:
                # This catches cases where repair_json or the second json.loads fails
                logger.error(f"Critical failure extracting OCR text: {e}. Raw response (first 100 characters): {raw_response[:100]}...")

        return ""


    @staticmethod
    def _split_into_blocks(text: str) -> List[str]:
        """
            Split text into logical Markdown blocks.
            Fenced code blocks and tables are kept intact as single blocks.
            """
        blocks: List[str] = []
        current_block: List[str] = []
        in_code_fence = in_table = False

        def flush():
            """Helper to join, strip, and save the current block content."""
            if content := "\n".join(current_block).strip():
                blocks.append(content)
            current_block.clear()

        for line in text.splitlines():
            stripped = line.strip()

            # 1. Handle Fenced Code Blocks (Highest Priority)
            if stripped.startswith("```"):
                in_code_fence = not in_code_fence
                current_block.append(line)
                continue

            if in_code_fence:
                current_block.append(line)
                continue

            # 2. Handle Tables and Paragraphs
            is_table_line = stripped.startswith("|") and stripped.endswith("|")

            if is_table_line:
                if not in_table:
                    flush()  # Entering a table, flush previous content
                in_table = True
                current_block.append(line)
            elif in_table:
                flush()      # Just left a table, flush it
                in_table = False
                if stripped:
                    current_block.append(line) # Preserve the line that ended the table
            elif not stripped:
                flush()      # Standard blank line block separator
            else:
                current_block.append(line)

        flush()  # Final flush for the remaining buffer
        return blocks
