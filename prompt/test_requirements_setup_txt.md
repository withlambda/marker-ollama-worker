# Context
This file, `test/requirements-setup.txt`, contains a minimal set of Python dependencies required to run the local test suite on the host before building the Docker image. Specifically, it is used to install `reportlab` for generating sample PDFs.

# Interface
The file follows the standard `requirements.txt` format with pinned versions for `charset-normalizer`, `pillow`, `reportlab`, `setuptools`, and `wheel`.

# Logic
The `test/run.sh` script installs these dependencies via `pip install -r requirements-setup.txt` to prepare the environment for generating input data. The specific pinned versions are:
- `charset-normalizer==3.4.4`
- `pillow==11.1.0`
- `reportlab==4.3.1`
- `setuptools==75.8.0`
- `wheel==0.45.1`

# Goal
The prompt file provides the exact dependency list and versions for the local test preparation phase to ensure a stable test environment.
