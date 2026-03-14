import os
import subprocess
import time
import logging
import signal
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, TextIO, Tuple
import ollama

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
    def __init__(self) -> None:
        """
        Initializes the OllamaWorker with the host from OLLAMA_BASE_URL
        and sets up the Ollama client.
        """
        self.host: str = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        # Configure the ollama client to point to our local instance
        self.client: ollama.Client = ollama.Client(host=self.host)
        self.log_file: Optional[TextIO] = None
        self.process: Optional[subprocess.Popen] = None

    def start_server(self) -> None:
        """
        Starts the Ollama server in the background.
        Opens a log file 'ollama.log' to capture server output and stderr.
        Waits for the server to be ready before returning.

        Raises:
            RuntimeError: If the Ollama server fails to start or become responsive.
        """
        if self.process is not None:
            logger.info("Ollama server is already running.")
            return

        logger.info("Starting Ollama service...")

        # Log environment info for debugging
        self._log_env_info()

        # Ensure OLLAMA_MODELS is set (usually handled by entrypoint scripts)
        if "OLLAMA_MODELS" not in os.environ:
             logger.warning("OLLAMA_MODELS environment variable not set.")

        self.log_file = open("ollama.log", "w")
        try:
            # Prepare environment for ollama serve
            env = os.environ.copy()
            # Enable debug logging in ollama if requested
            if os.environ.get("OLLAMA_DEBUG") == "1":
                logger.info("Enabling OLLAMA_DEBUG=1")
                env["OLLAMA_DEBUG"] = "1"

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

    def _log_env_info(self) -> None:
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

        for var in ["CUDA_VISIBLE_DEVICES", "NVIDIA_VISIBLE_DEVICES", "OLLAMA_MODELS", "OLLAMA_HOST"]:
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
        """Stops the Ollama server and its process group."""
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
            self.log_file.close()
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

        If OLLAMA_MODEL is set, it checks if the model exists and pulls it if not.
        If OLLAMA_MODEL is NOT set, it attempts to build a model from a local Hugging Face
        model cache directory, as specified by other environment variables.

        Raises:
            RuntimeError: If pulling or creating the model fails.
        """
        model_name = os.environ.get("OLLAMA_MODEL") or self._get_ollama_model_name_from_hf_specification(
            hf_model_name=os.environ.get("OLLAMA_HUGGING_FACE_MODEL_NAME"),
            hf_model_quantization=os.environ.get("OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION")
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
            # Case 2: No OLLAMA_MODEL - Build from HF
            self._build_from_hf()

        if not os.environ.get("OLLAMA_MODEL"):
            os.environ["OLLAMA_MODEL"] = model_name

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

        Uses HF_HOME, OLLAMA_HUGGING_FACE_MODEL_NAME, and OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION
        environment variables to locate the model files and construct the Modelfile.

        Raises:
            FileNotFoundError: If the model directory, snapshots, or GGUF files are missing.
            RuntimeError: If the Ollama model creation fails.
        """
        hf_home = os.environ.get("HF_HOME")
        model_name = os.environ.get("OLLAMA_HUGGING_FACE_MODEL_NAME")
        quantization = os.environ.get("OLLAMA_HUGGING_FACE_MODEL_QUANTIZATION")

        if not all([hf_home, model_name, quantization]):
             logger.info("Skipping Ollama build: Missing HF configuration.")
             return

        logger.info(f"Attempting to build Ollama model from HF: {model_name} ({quantization})")

        # Construct path: models--<user>--<repo>
        repo_dir_name = "models--" + model_name.replace("/", "--")
        base_path = Path(hf_home) / "hub" / repo_dir_name

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
        # Equivalent to: find . -name "*quantization*.gguf"
        gguf_files = list(snapshot_path.glob(f"*{quantization}*.gguf"))

        model_file = None
        adapter_file = None

        for f in gguf_files:
            if "mmproj" in f.name:
                adapter_file = f
            else:
                model_file = f

        if not model_file:
            raise FileNotFoundError(f"No GGUF file matching '{quantization}' found in {snapshot_path}")

        # Set OLLAMA_MODEL env var for the rest of the process
        # Ollama model names are typically lowercase.
        final_model_name = model_file.stem.lower()
        os.environ["OLLAMA_MODEL"] = final_model_name
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
        with tempfile.NamedTemporaryFile(mode='w', suffix='.Modelfile', delete=False) as tmp:
            tmp.write(modelfile_content)
            tmp_path = tmp.name

        try:
            # Use subprocess to create the model, as some versions of the Python SDK
            # have issues with the 'modelfile' keyword argument.
            # We ensure OLLAMA_HOST is set so it connects to the local server.
            env = os.environ.copy()
            env["OLLAMA_HOST"] = self.host

            logger.info(f"Creating model '{final_model_name}' using Ollama CLI and temporary Modelfile...")
            subprocess.run(
                ["ollama", "create", final_model_name, "-f", tmp_path],
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
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _process_single_chunk(
        self,
        chunk: str,
        system_prompt: str,
        chunk_index: int
    ) -> str:
        """
        Processes a single text chunk using the Ollama model.

        Args:
            chunk (str): The text chunk to process
            system_prompt (str): The system prompt to use
            chunk_index (int): The index of this chunk (for logging)

        Returns:
            str: The processed text chunk
        """
        model = os.environ.get("OLLAMA_MODEL")
        try:
            response = self.client.generate(
                model=model,
                prompt=chunk,
                system=system_prompt,
                stream=False
            )

            return self._extract_response_text(response)
        except Exception as e:
            logger.error(f"Exception processing chunk {chunk_index}: {e}")
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
        model = os.environ.get("OLLAMA_MODEL")
        if not model:
            raise ValueError("OLLAMA_MODEL not set for processing")

        chunks = self._chunk_text(text)

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
        model = os.environ.get("OLLAMA_MODEL")
        if not model:
            raise ValueError("OLLAMA_MODEL not set for image description")

        system_prompt = prompt_template if prompt_template else (
            "You are an expert document-vision assistant. "
            "Describe the provided image precisely and factually. "
            "Include visible text, tables, charts, figures, equations, and layout details when present. "
            "Do not infer details that are not visible."
        )

        try:
            response = self.client.generate(
                model=model,
                prompt="Provide a precise and concise description of this image.",
                system=system_prompt,
                images=[str(image_path)],
                stream=False
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

    @staticmethod
    def _chunk_text(
        text: str,
        chunk_size: Optional[int] = None
    ) -> List[str]:
        """
        Splits text into chunks of approximately chunk_size characters,
        trying to break on newlines.

        Args:
            text (str): The text to chunk
            chunk_size (int): Maximum characters per chunk. If None, uses OLLAMA_CHUNK_SIZE env var.

        Returns:
            list: List of text chunks
        """
        if chunk_size is None:
            chunk_size = int(os.environ.get("OLLAMA_CHUNK_SIZE", "4000"))

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
        model = os.environ.get("OLLAMA_MODEL")
        if not model:
            return
        try:
             # Use client.generate with keep_alive=0
             self.client.generate(
                 model=model,
                 prompt="",
                 keep_alive=0
             )
             logger.info("Requested Ollama model unload.")
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
