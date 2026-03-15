import os
import subprocess
import time
import logging
import signal
import tempfile
import random
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, TextIO, Tuple
import ollama
from settings import OllamaSettings

# Configure logging
logger = logging.getLogger(__name__)

class OllamaWorker:
    """
    Manages the Ollama server lifecycle and handles LLM text processing tasks.

    This class provides methods to:
    - Start and stop the Ollama server in a separate process.
    - Ensure the required LLM model is available (pull or build from Hugging Face).
    - Process text chunks in parallel using the Ollama model for OCR correction.
    - Handle model unloading to free up VRAM for other tasks.
    """
    def __init__(
        self,
        settings: Optional[OllamaSettings] = None,
        **kwargs
    ) -> None:
        """
        Initializes the OllamaWorker with configuration from an OllamaSettings object
        or from keyword arguments (which override environment variables).
        """
        if settings is None:
            # Filter kwargs to only include valid fields for OllamaSettings
            # although extra='ignore' is set, it's safer to be explicit or just pass them.
            settings = OllamaSettings(**kwargs)

        self.settings = settings

        # Host and Client
        self.host: str = settings.host
        self.client: ollama.Client = ollama.Client(host=self.host)

        # Model configuration
        self.model: Optional[str] = settings.model
        self.hf_model_name: Optional[str] = settings.hf_model_name
        self.hf_model_quantization: Optional[str] = settings.hf_model_quantization
        self.hf_home: Optional[str] = settings.hf_home
        self.models_dir: Optional[str] = settings.models_dir

        # Runtime configuration
        self.max_retries: int = settings.max_retries
        self.retry_delay: float = settings.retry_delay
        self.context_length: int = settings.context_length
        self.chunk_size: int = settings.chunk_size
        self.image_description_prompt: Optional[str] = settings.image_description_prompt

        # Server configuration (used when starting the server)
        self.flash_attention: str = settings.flash_attention
        self.keep_alive: str = settings.keep_alive
        self.log_dir: str = settings.log_dir or "."
        self.debug: str = settings.debug
        self.num_parallel: Optional[str] = str(settings.num_parallel) if settings.num_parallel is not None else None
        self.max_loaded_models: Optional[str] = str(settings.max_loaded_models) if settings.max_loaded_models is not None else None
        self.kv_cache_type: Optional[str] = settings.kv_cache_type
        self.max_queue: Optional[str] = str(settings.max_queue) if settings.max_queue is not None else None

        self.log_file: Optional[TextIO] = None
        self.process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

        logger.info(f"OllamaWorker initialized with host={self.host}, model={self.model}")

    def __del__(self) -> None:
        """
        Ensures that the Ollama server is stopped and resources are released
        when the worker object is destroyed.
        """
        self.stop_server()


    def start_server(self) -> None:
        """
        Starts the Ollama server in the background.
        Opens a log file 'ollama.log' to capture server output and stderr.
        Waits for the server to be ready before returning.

        Raises:
            RuntimeError: If the Ollama server fails to start or become responsive.
        """
        with self._lock:
            if self.process is not None:
                if self.process.poll() is None:
                    logger.info("Ollama server is already running.")
                    return
                else:
                    logger.warning("Ollama server process was found dead. Cleaning up before restart.")
                    self.stop_server()

            logger.info("Starting Ollama service...")

            # Log environment info for debugging
            self._log_env_info()

            # Ensure OLLAMA_MODELS is set (handled by setup_config() in utils.py)
            if not self.models_dir:
                 logger.warning("OLLAMA_MODELS environment variable not set and models_dir not provided.")

            log_file_path = os.path.join(self.log_dir, "ollama.log")

            # Ensure the log directory exists if it's not the current directory
            if self.log_dir != ".":
                os.makedirs(self.log_dir, exist_ok=True)

            logger.info(f"Ollama server logs will be written to: {log_file_path}")
            self.log_file = open(log_file_path, "w")
            try:
                # Prepare environment for ollama serve
                env = os.environ.copy()

                # Apply instance configuration to server environment
                env["OLLAMA_HOST"] = self.host
                env["OLLAMA_FLASH_ATTENTION"] = self.flash_attention
                env["OLLAMA_KEEP_ALIVE"] = self.keep_alive
                env["OLLAMA_DEBUG"] = self.debug

                if self.models_dir:
                    env["OLLAMA_MODELS"] = self.models_dir
                if self.num_parallel:
                    env["OLLAMA_NUM_PARALLEL"] = self.num_parallel
                if self.max_loaded_models:
                    env["OLLAMA_MAX_LOADED_MODELS"] = self.max_loaded_models
                if self.kv_cache_type:
                    env["OLLAMA_KV_CACHE_TYPE"] = self.kv_cache_type
                if self.max_queue:
                    env["OLLAMA_MAX_QUEUE"] = self.max_queue

                # Start ollama serve
                self.process = subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=self.log_file,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    env=env
                )
                logger.info(f"OLLAMA PID: {self.process.pid}")
                self._wait_for_ready()
            except Exception as e:
                logger.error(f"Failed to start Ollama: {e}")
                self.stop_server()
                raise

    @staticmethod
    def _log_env_info() -> None:
        """Logs environment information relevant to GPU and Ollama."""
        logger.info("--- Environment Info ---")
        try:
            import torch
            if torch.cuda.is_available():
                logger.info(f"Torch CUDA available: YES (Device: {torch.cuda.get_device_name(0)})")
                try:
                    # Get device properties for total memory
                    props = torch.cuda.get_device_properties(0)
                    total_gb = props.total_memory / 1024**3

                    # Get free/total memory using mem_get_info if available (since 1.10)
                    free_gb_info = ""
                    if hasattr(torch.cuda, "mem_get_info"):
                        free, total = torch.cuda.mem_get_info(0)
                        free_gb_info = f", {free / 1024**3:.2f} GB free"

                    logger.info(f"Torch CUDA memory: {total_gb:.2f} GB total{free_gb_info}")
                except Exception as e:
                    logger.warning(f"Could not retrieve detailed GPU memory info: {e}")
            else:
                logger.warning("Torch CUDA available: NO")
        except ImportError:
            logger.warning("Torch not available for GPU check.")

        for var in [
            "CUDA_VISIBLE_DEVICES", "NVIDIA_VISIBLE_DEVICES",
            "OLLAMA_MODELS", "OLLAMA_LOGS", "OLLAMA_HOST",
            "OLLAMA_NUM_PARALLEL", "OLLAMA_MAX_LOADED_MODELS",
            "OLLAMA_FLASH_ATTENTION", "OLLAMA_KV_CACHE_TYPE",
            "OLLAMA_MAX_QUEUE", "OLLAMA_KEEP_ALIVE"
        ]:
            if var in os.environ:
                logger.info(f"{var}: {os.environ[var]}")

        # Check if nvidia-smi is available
        try:
            res = subprocess.check_output(["nvidia-smi", "-L"], encoding="utf-8")
            logger.info(f"Nvidia-SMI: {res.strip()}")
        except Exception:
            logger.warning("Nvidia-SMI not available.")
        logger.info("------------------------")

    def stop_server(self) -> None:
        """
        Stops the Ollama server and its process group.
        Ensures resources (process, log file handle) are released.
        """
        with self._lock:
            if self.process:
                logger.info(f"Stopping Ollama service (PID: {self.process.pid})...")
                try:
                    # Since we used start_new_session=True, we should kill the process group
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)

                    # Still call wait to cleanup the zombie process
                    self.process.wait(timeout=10)
                except ProcessLookupError:
                    logger.debug("Ollama process already gone.")
                except subprocess.TimeoutExpired:
                    logger.warning("Ollama process group did not terminate gracefully, killing...")
                    try:
                        os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                        self.process.wait()
                    except Exception as e:
                        logger.error(f"Failed to kill Ollama process group: {e}")
                except Exception as e:
                    logger.error(f"Error while stopping Ollama: {e}")
                    # Fallback to simple terminate
                    self.process.terminate()
                    self.process.wait(timeout=5)

                logger.info("Ollama service stopped.")
                self.process = None

            if self.log_file:
                try:
                    self.log_file.close()
                except Exception as e:
                    logger.error(f"Error closing Ollama log file: {e}")
                finally:
                    self.log_file = None

    def _wait_for_ready(
        self,
        max_retries: int = 30
    ) -> None:
        """
        Waits for the Ollama server to be responsive by polling the list API.

        Args:
            max_retries (int): Maximum number of polling attempts (2 seconds between attempts).

        Raises:
            RuntimeError: If the Ollama server fails to start or become responsive within the timeout.
        """
        logger.info("Waiting for Ollama to start...")
        for i in range(max_retries):
            try:
                # Simple health check using requests or client.list()
                self.client.list()
                logger.info("Ollama is up and running!")
                return
            except Exception:
                pass

            if self.process and self.process.poll() is not None:
                raise RuntimeError("Ollama process exited unexpectedly.")

            logger.info(f"Waiting for Ollama... ({i+1}/{max_retries})")
            time.sleep(2)

        raise RuntimeError("Ollama failed to start within the timeout period.")

    def ensure_model(self) -> None:
        """
        Ensures the configured model exists in the Ollama instance.

        If model is specified, it checks if it exists and pulls it if not.
        If model is NOT specified, it attempts to build a model from a local Hugging Face
        model cache directory, as specified by other configuration.

        Raises:
            RuntimeError: If pulling or creating the model fails.
        """
        model_name = self.model or self._get_ollama_model_name_from_hf_specification(
            hf_model_name=self.hf_model_name,
            hf_model_quantization=self.hf_model_quantization
        )

        if model_name:
            # Case 1: Model Name specified - Check/Pull
            if not self._check_model_exists(model_name):
                logger.info(f"Model '{model_name}' not found. Pulling from registry...")
                try:
                    # Use the client to pull
                    self.client.pull(model_name)
                    logger.info(f"Successfully pulled model '{model_name}'")
                except Exception as e:
                    raise RuntimeError(f"Failed to pull model '{model_name}': {e}")
            else:
                logger.info(f"Model '{model_name}' found locally.")
        else:
            # Case 2: No model - Build from HF
            self._build_from_hf()

        if not self.model:
            self.model = model_name

    @staticmethod
    def _get_ollama_model_name_from_hf_specification(
        hf_model_name: str,
        hf_model_quantization: str
    ) -> str:
        """
        Convert the Hugging Face model specification into an Ollama model name.

        The method takes a Hugging Face model name and quantization specification,
        then converts this information into the specific format required for Ollama
        model names. If the model name contains a path element (e.g., "namespace/model"),
        only the portion after the "/" is used as the base name. The quantization
        specification is then appended to this base name, separated by a hyphen.

        :param hf_model_name: The name of the Hugging Face model. It can include a namespace or subpath
                              separated by a forward slash.
        :param hf_model_quantization: The quantization level of the Hugging Face model, which must be
                                       compatible with the Ollama format.
        :return: A string representing the transformed Ollama model name formatted as
                 "<base_name>-<quantization>".
        """
        ollama_base_name = hf_model_name if '/' not in hf_model_name else hf_model_name.split('/',1)[1]

        return (ollama_base_name + "-" + hf_model_quantization).lower()

    def _check_model_exists(
        self,
        model_name: str
    ) -> bool:
        """
        Checks if a model with the given name exists in the local Ollama registry.

        Args:
            model_name (str): Name of the model to check.

        Returns:
            bool: True if the model (or a tagged version) exists, False otherwise.
        """
        try:
            response = self.client.list()
            # Handle both list of dicts and object with models attribute
            if hasattr(response, 'models'):
                models_list = response.models
            elif isinstance(response, dict):
                models_list = response.get('models', [])
            else:
                models_list = []

            # Extract names
            names = []
            for model in models_list:
                if isinstance(model, dict):
                    names.append(model.get('name', ''))
                elif hasattr(model, 'model'): # Newer versions might have 'model' attribute
                    names.append(model.model)
                elif hasattr(model, 'name'):
                    names.append(model.name)

            # Check for exact or tag match
            model_name_lower = model_name.lower()
            names_lower = [n.lower() for n in names]
            return model_name_lower in names_lower or any(m.startswith(f"{model_name_lower}:") for m in names_lower)
        except Exception as e:
            logger.debug(f"Error checking model existence: {e}")
            return False

    def _build_from_hf(self) -> None:
        """
        Builds an Ollama model from GGUF files found in a Hugging Face cache.

        Uses hf_home, hf_model_name, and hf_model_quantization configuration to
        locate the model files and construct the Modelfile.

        Raises:
            FileNotFoundError: If the model directory, snapshots, or GGUF files are missing.
            RuntimeError: If the Ollama model creation fails.
        """
        if not all([self.hf_home, self.hf_model_name, self.hf_model_quantization]):
             logger.info("Skipping Ollama build: Missing HF configuration.")
             return

        logger.info(f"Attempting to build Ollama model from HF: {self.hf_model_name} ({self.hf_model_quantization})")

        # Construct path: models--<user>--<repo>
        repo_dir_name = "models--" + self.hf_model_name.replace("/", "--")
        base_path = Path(self.hf_home) / "hub" / repo_dir_name

        if not base_path.exists():
            raise FileNotFoundError(f"Hugging Face model directory not found: {base_path}")

        # Find snapshot (refs/main or first dir)
        refs_main = base_path / "refs" / "main"
        if refs_main.exists():
            ref = refs_main.read_text().strip()
            snapshot_path = base_path / "snapshots" / ref
        else:
            # Fallback to first snapshot
            snapshots_dir = base_path / "snapshots"
            if snapshots_dir.exists():
                snapshots = [d for d in snapshots_dir.iterdir() if d.is_dir()]
                if snapshots:
                    snapshot_path = snapshots[0]
                else:
                    raise FileNotFoundError(f"No snapshots found in {snapshots_dir}")
            else:
                 raise FileNotFoundError(f"Snapshots directory not found in {base_path}")

        logger.info(f"Using snapshot: {snapshot_path}")

        # Find GGUF file
        # Equivalent to: find . -name "*hf_model_quantization*.gguf"
        gguf_files = list(snapshot_path.glob(f"*{self.hf_model_quantization}*.gguf"))

        model_file = None
        adapter_file = None

        for f in gguf_files:
            if "mmproj" in f.name:
                adapter_file = f
            else:
                model_file = f

        if not model_file:
            raise FileNotFoundError(f"No GGUF file matching '{self.hf_model_quantization}' found in {snapshot_path}")

        # Set self.model for the rest of the process
        # Ollama model names are typically lowercase.
        final_model_name = model_file.stem.lower()
        self.model = final_model_name
        logger.info(f"Resolved Ollama Model Name: {final_model_name}")

        if self._check_model_exists(final_model_name):
            logger.info(f"Ollama model '{final_model_name}' already exists.")
            return

        logger.info(f"Building Ollama model '{final_model_name}'...")

        # Prepare Modelfile content
        # Quoting paths in the Modelfile is recommended to avoid issues with special characters.
        modelfile_content = f'FROM "{model_file.absolute()}"\n'
        if adapter_file:
            modelfile_content += f'ADAPTER "{adapter_file.absolute()}"\n'

        # Use a temporary file for the Modelfile to ensure better compatibility with the Ollama CLI.
        # Some versions of the CLI have issues with reading from stdin (-f -).
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.Modelfile', delete=False) as tmp:
                tmp.write(modelfile_content)
                tmp_path = Path(tmp.name)

            # Use subprocess to create the model, as some versions of the Python SDK
            # have issues with the 'modelfile' keyword argument.
            # We ensure OLLAMA_HOST is set so it connects to the local server.
            env = os.environ.copy()
            env["OLLAMA_HOST"] = self.host

            logger.info(f"Creating model '{final_model_name}' using Ollama CLI and temporary Modelfile...")
            subprocess.run(
                ["ollama", "create", final_model_name, "-f", str(tmp_path)],
                check=True,
                env=env,
                capture_output=True
            )
            logger.info(f"Successfully created model '{final_model_name}'")
        except subprocess.CalledProcessError as e:
            error_detail = e.stderr.decode().strip() if e.stderr else str(e)
            raise RuntimeError(f"Failed to create model '{final_model_name}' via CLI: {error_detail}")
        except Exception as e:
            raise RuntimeError(f"Failed to create model '{final_model_name}': {e}")
        finally:
            if tmp_path:
                tmp_path.unlink(missing_ok=True)

    def _process_single_chunk(
        self,
        chunk: str,
        system_prompt: str,
        chunk_index: int
    ) -> str:
        """
        Processes a single text chunk using the Ollama model with retry logic.

        Args:
            chunk (str): The text chunk to process
            system_prompt (str): The system prompt to use
            chunk_index (int): The index of this chunk (for logging)

        Returns:
            str: The processed text chunk
        """
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.generate(
                    model=self.model,
                    prompt=chunk,
                    system=system_prompt,
                    stream=False,
                    options={
                        "num_ctx": self.context_length
                    }
                )
                return self._extract_response_text(response)
            except Exception as e:
                error_msg = str(e).lower()
                is_last_attempt = (attempt == self.max_retries)

                # Identify retryable errors
                # "model runner has unexpectedly stopped" usually means OOM or crash of the backend
                # "connection refused" means the server might be restarting or crashed
                retryable = any(msg in error_msg for msg in [
                    "model runner has unexpectedly stopped",
                    "connection refused",
                    "try again",
                    "overloaded",
                    "timeout",
                    "503",
                    "504"
                ])

                if retryable and not is_last_attempt:
                    # Exponential backoff with jitter
                    delay = (self.retry_delay * (2 ** attempt)) + (random.random() * self.retry_delay)
                    logger.warning(
                        f"Retryable error processing chunk {chunk_index} "
                        f"(attempt {attempt + 1}/{self.max_retries + 1}). "
                        f"Retrying in {delay:.2f}s... Error: {e}"
                    )

                    # If it was a connection refused, check if server process is actually alive
                    if "connection refused" in error_msg and self.process:
                        if self.process.poll() is not None:
                            logger.error(f"Ollama server process died (PID {self.process.pid}). "
                                         f"Attempting to restart...")
                            # start_server handles the lock and re-initialization
                            try:
                                self.start_server()
                            except Exception as start_err:
                                logger.error(f"Failed to restart Ollama server: {start_err}")

                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"Fatal error processing chunk {chunk_index} after {attempt + 1} attempts: {e}")
                    return chunk  # Fallback to original

    @staticmethod
    def _extract_response_text(response: object) -> str:
        """
        Normalizes Ollama SDK responses to a plain string.

        Args:
            response (object): Response object from `ollama.Client.generate`.

        Returns:
            str: Extracted response text.
        """
        if isinstance(response, dict):
            return str(response.get("response", "")).strip()
        if hasattr(response, "response"):
            return str(response.response).strip()
        return str(response).strip()

    def process_text(
        self,
        text: str,
        prompt_template: Optional[str],
        max_chunk_workers: int
    ) -> str:
        """
        Post-processes text using the loaded Ollama model.
        Chunks the text to avoid context window issues.
        Supports parallel chunk processing for improved performance.

        Args:
            text (str): The text to process
            prompt_template (str): Optional custom prompt template
            max_chunk_workers (int): Maximum number of parallel workers for chunk processing.

        Returns:
            str: The processed text
        """
        if not self.model:
            raise ValueError("model not set for processing")

        chunks = self._chunk_text(text, self.chunk_size)

        # Default prompt if none provided
        system_prompt = prompt_template if prompt_template else (
            "You are a helpful assistant. Correct the OCR errors in the text provided below. "
            "Output ONLY the corrected text, maintaining original formatting as much as possible."
        )

        # Determine optimal worker count
        max_workers =  max(1, int(max_chunk_workers))

        logger.info(f"Processing {len(chunks)} chunks with Ollama using {max_workers} parallel workers...")

        # Single-threaded processing for small workloads or when max_workers=1
        if max_workers == 1 or len(chunks) == 1:
            corrected_chunks = []
            for i, chunk in enumerate(chunks):
                result = self._process_single_chunk(chunk, system_prompt, i)
                corrected_chunks.append(result)
        else:
            # Parallel chunk processing
            corrected_chunks = [None] * len(chunks)

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all chunks for processing
                future_to_index = {
                    executor.submit(self._process_single_chunk, chunk, system_prompt, i): i
                    for i, chunk in enumerate(chunks)
                }

                # Collect results in original order
                for future in as_completed(future_to_index):
                    idx = future_to_index[future]
                    try:
                        corrected_chunks[idx] = future.result()
                    except Exception as e:
                        logger.error(f"Exception collecting result for chunk {idx}: {e}")
                        corrected_chunks[idx] = chunks[idx]  # Fallback to original

        return "\n\n".join(corrected_chunks)

    def process_file(
        self,
        file_path: Path,
        prompt_template: Optional[str],
        max_chunk_workers: int,
    ) -> bool:
        """
        Processes a single file with the Ollama model.
        Reads the file, processes its content, and overwrites it.

        Args:
            file_path (Path): Path to the file to process
            prompt_template (str): Optional custom prompt template
            max_chunk_workers (int): Maximum number of parallel workers for chunk processing.

        Returns:
            bool: True if processing was successful, False otherwise
        """
        if not file_path.exists():
            return False

        logger.info(f"LLM Processing: {file_path.name}")
        try:
            original_text = file_path.read_text(encoding="utf-8")
            processed_text = self.process_text(
                text=original_text,
                prompt_template=prompt_template,
                max_chunk_workers=max_chunk_workers
            )

            # Overwrite the file with processed text
            file_path.write_text(processed_text, encoding="utf-8")
            logger.info(f"Finished LLM processing for {file_path.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to post-process {file_path.name}: {e}")
            return False

    def _describe_single_image(
        self,
        image_path: Path,
        prompt_template: Optional[str],
        image_index: int
    ) -> Optional[str]:
        """
        Generates a description for a single image using the Ollama model.

        Args:
            image_path (Path): Path to the image.
            prompt_template (Optional[str]): Optional custom prompt for image description.
            image_index (int): Zero-based image index for logging.

        Returns:
            Optional[str]: Description text, or None when generation fails.
        """
        if not self.model:
            raise ValueError("model not set for image description")

        system_prompt = prompt_template if prompt_template else (
            "You are an expert document-vision assistant. "
            "Describe the provided image precisely and factually. "
            "Include visible text, tables, charts, figures, equations, and layout details when present. "
            "Do not infer details that are not visible."
        )

        try:
            response = self.client.generate(
                model=self.model,
                prompt="Provide a precise and concise description of this image.",
                system=system_prompt,
                images=[str(image_path)],
                stream=False,
                options={
                    "num_ctx": self.context_length
                }
            )
            description = self._extract_response_text(response)
            if not description:
                logger.warning(f"Empty image description returned for {image_path.name}")
                return None
            return description
        except Exception as e:
            logger.error(f"Failed to describe image {image_index + 1} ({image_path.name}): {e}")
            return None

    def describe_images(
        self,
        image_paths: List[Path],
        prompt_template: Optional[str],
        max_image_workers: int,
    ) -> List[Tuple[Path, str]]:
        """
        Generates descriptions for multiple images.

        Args:
            image_paths (List[Path]): Paths of images to describe.
            prompt_template (Optional[str]): Optional custom image description prompt.
            max_image_workers (int): Maximum number of parallel workers.

        Returns:
            List[Tuple[Path, str]]: Successfully described image/path tuples in original order.
        """
        if not image_paths:
            return []

        max_workers = max(1, int(max_image_workers))
        logger.info(f"Describing {len(image_paths)} extracted images with {max_workers} worker(s)...")

        descriptions: List[Optional[str]] = [None] * len(image_paths)

        if max_workers == 1 or len(image_paths) == 1:
            for i, image_path in enumerate(image_paths):
                descriptions[i] = self._describe_single_image(
                    image_path=image_path,
                    prompt_template=prompt_template,
                    image_index=i
                )
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_index = {
                    executor.submit(self._describe_single_image, image_path, prompt_template, i): i
                    for i, image_path in enumerate(image_paths)
                }

                for future in as_completed(future_to_index):
                    idx = future_to_index[future]
                    try:
                        descriptions[idx] = future.result()
                    except Exception as e:
                        logger.error(f"Exception collecting image description {idx + 1}: {e}")
                        descriptions[idx] = None

        return [
            (image_path, description)
            for image_path, description in zip(image_paths, descriptions)
            if description
        ]

    def _chunk_text(
        self,
        text: str,
        chunk_size: Optional[int] = None
    ) -> List[str]:
        """
        Splits text into chunks of approximately chunk_size characters,
        trying to break on newlines.

        Args:
            text (str): The text to chunk
            chunk_size (int): Maximum characters per chunk. If None, uses self.chunk_size.

        Returns:
            list: List of text chunks
        """
        if chunk_size is None:
            chunk_size = self.chunk_size

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = start + chunk_size
            if end >= text_len:
                chunks.append(text[start:])
                break

            # Try to find the last newline within the chunk limit
            # Look back from 'end' up to 'start'
            last_newline = text.rfind('\n', start, end)

            if last_newline != -1 and last_newline > start:
                # Break at newline
                chunks.append(text[start:last_newline])
                start = last_newline + 1 # Skip the newline char
            else:
                # Force break if no newline found (unlikely in md, but possible)
                chunks.append(text[start:end])
                start = end

        return chunks

    def unload_model(self) -> None:
        """
        Unloads the current model from VRAM by sending a generate request with keep_alive=0.
        This allows other processes (like marker) to utilize the VRAM.
        """
        if not self.model:
            return
        try:
             # Use client.generate with keep_alive=0
             self.client.generate(
                 model=self.model,
                 prompt="",
                 keep_alive=0
             )
             logger.info(f"Requested Ollama model unload for '{self.model}'.")
        except Exception as e:
            logger.error(f"Error unloading model: {e}")

    def initialize_model(self) -> bool:
        """
        Initializes Ollama server and ensures the model is ready.
        Stops the server after verification to free VRAM.

        Returns:
            bool: True if initialization succeeded, False otherwise
        """
        logger.info("--- initializing Ollama for model setup ---")
        try:
            self.start_server()
            self.ensure_model()
            logger.info("Ollama model setup complete. Stopping server to free VRAM for Marker.")
            return True
        except Exception as e:
            logger.error(f"Failed during Ollama model setup: {e}")
            logger.warning("Proceeding with Marker conversion without LLM capability check.")
            return False
        finally:
            self.stop_server()
