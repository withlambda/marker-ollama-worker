import sys
import os
import subprocess
import importlib

def check_import(module_name: str) -> bool:
    """Attempts to import a module and returns True if successful, False otherwise."""
    try:
        importlib.import_module(module_name)
        print(f"✅ Success: '{module_name}' imported.")
        return True
    except ImportError as e:
        print(f"❌ Error: '{module_name}' NOT found ({e}).")
        return False
    except Exception as e:
        print(f"❌ Error during import of '{module_name}': {e}")
        return False

def check_vllm_entrypoint() -> bool:
    """Checks if the vLLM entrypoint is functional by running its imports.
    Instead of full --help (which triggers device inference), we try to import
    the main entrypoint module.
    """
    print("Checking vLLM entrypoint imports ('python3 -c \"import vllm.entrypoints.openai.api_server\"')...")

    # Set environment variables to force CPU and skip GPU inference during build
    env = os.environ.copy()
    env["VLLM_TARGET_DEVICE"] = "cpu"
    env["VLLM_DEVICE"] = "cpu"
    env["VLLM_CONFIGURE_LOGGING"] = "0"
    env["VLLM_LOGGING_LEVEL"] = "ERROR"

    try:
        # We only want to ensure the code *can* be loaded (imports work)
        # Some vLLM versions might still trigger logic on import, so we use CPU flags
        # If it still fails with device error, we look for 'ModuleNotFoundError'
        # which is what we REALLY care about.
        result = subprocess.run(
            ["python3", "-c", "import vllm.entrypoints.openai.api_server"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )
        if result.returncode == 0:
            print("✅ Success: vLLM entrypoint imports are working.")
            return True
        else:
            stderr = result.stderr or ""
            if "RuntimeError: Failed to infer device type" in stderr and "ModuleNotFoundError" not in stderr:
                print("⚠️  Warning: vLLM entrypoint import triggered device inference failure (build environment).")
                print("   However, no ModuleNotFoundError was detected, so dependencies likely exist.")
                return True

            print(f"❌ Error: vLLM entrypoint import failed with exit code {result.returncode}.")
            print(f"--- stderr ---\n{result.stderr}\n--------------")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Error: vLLM entrypoint import check timed out.")
        return False
    except Exception as e:
        print(f"❌ Error checking vLLM entrypoint: {e}")
        return False

def main():
    modules_to_check = [
        "psutil",
        "requests",
        "mineru",
        "paddle",
        "shapely",
        "runpod",
        "openai",
        "httpx",
        "tiktoken",
        "vllm",
        "pydantic",
        "pydantic_settings",
        "cv2",
        "starlette",
        "numpy",
        "google.protobuf",
        "filelock",
        "cuda",
    ]

    all_ok = True
    print("--- Starting Dependency Check ---")

    for mod in modules_to_check:
        if not check_import(mod):
            all_ok = False

    # Explicitly check the sub-package that caused the issue if vllm is present
    if "vllm" in sys.modules or check_import("vllm"):
        if not check_vllm_entrypoint():
            all_ok = False

    print("---------------------------------")
    if all_ok:
        print("🎉 All critical dependencies are verified!")
        sys.exit(0)
    else:
        print("🛑 Missing or broken dependencies found!")
        sys.exit(1)

if __name__ == "__main__":
    main()
