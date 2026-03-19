# Context
This file, `test/marker.env`, is a template for the environment variables that the `marker-pdf` library uses for its own configuration (e.g., paths for fonts and artifacts).

# Interface
The file contains various commented-out variables (`BASE_DIR`, `OUTPUT_DIR`, `FONT_DIR`, etc.) that can be un-commented and set if specific Marker internal overrides are needed.

# Logic
The file is a standard shell-compatible environment file. It is used by `docker run` via the `--env-file` flag in `test/run.sh`.

# Goal
The prompt file provides the template structure for Marker-specific environment configuration.
