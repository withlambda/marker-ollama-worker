import os
import subprocess
import time
import logging
import signal
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, TextIO
import ollama

# Configure logging
logger = logging.getLogger(__name__)

class OllamaWorker:
    def __init__(self) -> None:
        self.host: str = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        # Configure the ollama client to point to our local instance
        self.client: ollama.Client = ollama.Client(host=self.host)
        self.log_file: Optional[TextIO] = None
        self.process: Optional[subprocess.Popen] = None

    def start_server(self) -> None:
        """Starts the Ollama server in the background."""
        if self.process is not None:
            logger.info("Ollama server is already running.")
            return

        logger.info("Starting Ollama service...")

        # Ensure OLLAMA_MODELS is set (usually handled by entrypoint scripts)
        if "OLLAMA_MODELS" not in os.environ:
             logger.warning("OLLAMA_MODELS environment variable not set.")

        self.log_file = open("ollama.log", "w")
        try:
            # Start ollama serve
            self.process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=self.log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True
            )
            logger.info(f"OLLAMA PID: {self.process.pid}")
            self._wait_for_ready()
        except Exception as e:
            logger.error(f"Failed to start Ollama: {e}")
            self.stop_server()
            raise

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
        """Waits for the Ollama server to be responsive."""
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
        Ensures the configured model exists.
        Pulls it if specified by OLLAMA_MODEL, or builds it from HF cache if not.
        """
        model_name = os.environ.get("OLLAMA_MODEL")

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

    def _check_model_exists(
        self,
        model_name: str
    ) -> bool:
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
            return model_name in names or any(m.startswith(f"{model_name}:") for m in names)
        except Exception as e:
            logger.debug(f"Error checking model existence: {e}")
            return False

    def _build_from_hf(self) -> None:
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
        final_model_name = model_file.stem
        os.environ["OLLAMA_MODEL"] = final_model_name
        logger.info(f"Resolved Ollama Model Name: {final_model_name}")

        if self._check_model_exists(final_model_name):
            logger.info(f"Ollama model '{final_model_name}' already exists.")
            return

        logger.info(f"Building Ollama model '{final_model_name}'...")

        # Prepare Modelfile content
        modelfile_content = f"FROM {model_file.absolute()}\n"
        if adapter_file:
            modelfile_content += f"ADAPTER {adapter_file.absolute()}\n"

        try:
            # Use client.create instead of subprocess
            self.client.create(model=final_model_name, modelfile=modelfile_content)
            logger.info(f"Successfully created model '{final_model_name}'")
        except Exception as e:
            raise RuntimeError(f"Failed to create model '{final_model_name}': {e}")

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

            # Handle response duality
            if isinstance(response, dict):
                result = response.get("response", "")
            elif hasattr(response, 'response'):
                result = response.response
            else:
                result = str(response)

            return result
        except Exception as e:
            logger.error(f"Exception processing chunk {chunk_index}: {e}")
            return chunk  # Fallback to original

    def process_text(
        self,
        text: str,
        prompt_template: Optional[str] = None,
        max_chunk_workers: Optional[int] = None
    ) -> str:
        """
        Post-processes text using the loaded Ollama model.
        Chunks the text to avoid context window issues.
        Supports parallel chunk processing for improved performance.

        Args:
            text (str): The text to process
            prompt_template (str): Optional custom prompt template
            max_chunk_workers (int): Maximum number of parallel workers for chunk processing.
                                    If None, uses OLLAMA_CHUNK_WORKERS env var or auto-detection.

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
        max_workers = self._get_optimal_chunk_workers(len(chunks), max_chunk_workers)

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
        prompt_template: Optional[str] = None,
        max_chunk_workers: Optional[int] = None
    ) -> bool:
        """
        Processes a single file with the Ollama model.
        Reads the file, processes its content, and overwrites it.

        Args:
            file_path (Path): Path to the file to process
            prompt_template (str): Optional custom prompt template
            max_chunk_workers (int): Maximum number of parallel workers for chunk processing.
                                    If None, uses OLLAMA_CHUNK_WORKERS env var or auto-detection.

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

    @staticmethod
    def _get_optimal_chunk_workers(num_chunks: int, max_chunk_workers: Optional[int] = None) -> int:
        """
        Determines the optimal number of parallel workers for chunk processing.

        Args:
            num_chunks (int): Number of chunks to process
            max_chunk_workers (int): Explicitly requested worker count. If None, uses env var or auto-detection.

        Returns:
            int: Optimal number of workers
        """
        # Use explicit parameter if provided
        if max_chunk_workers is not None:
            # Respect chunk count - no point in more workers than chunks
            return min(max(1, max_chunk_workers), num_chunks)

        # Check environment variable
        chunk_workers_env = os.environ.get("OLLAMA_CHUNK_WORKERS", "auto").strip().lower()

        if chunk_workers_env != "auto":
            try:
                configured_workers = max(1, int(chunk_workers_env))
                # Respect chunk count - no point in more workers than chunks
                return min(configured_workers, num_chunks)
            except ValueError:
                logger.warning(f"Invalid OLLAMA_CHUNK_WORKERS value: {chunk_workers_env}, using auto")

        # Auto-detection based on chunk count and estimated VRAM
        total_vram = int(os.environ.get("TOTAL_VRAM_GB", "24"))
        vram_per_worker = int(os.environ.get("OLLAMA_VRAM_PER_WORKER", "5"))

        # Calculate max workers based on VRAM
        max_vram_workers = max(1, (total_vram - 4) // vram_per_worker)  # Reserve 4GB for overhead

        # Limit by number of chunks (no point in more workers than chunks)
        optimal_workers = min(max_vram_workers, num_chunks)

        # Cap at reasonable maximum (4 workers)
        optimal_workers = min(optimal_workers, 4)

        return optimal_workers

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
        """Unloads the model from VRAM by sending an empty request with keep_alive=0"""
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
