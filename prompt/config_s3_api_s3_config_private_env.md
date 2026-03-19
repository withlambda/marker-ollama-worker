# Context
This file, `config/s3-api/s3-config.private.env`, defines the S3 bucket configuration for the RunPod environment. It is sourced by `aws-commands.sh` to determine the target for S3 operations.

# Interface

## Variables
- `BUCKET_NAME`: The name of the S3 bucket (e.g., `474vekwnut`).
- `ENDPOINT_URL`: The custom S3 API endpoint URL provided by RunPod (e.g., `https://s3api-eu-cz-1.runpod.io`).
- `REGION`: The S3 region (e.g., `eu-cz-1`).

# Logic
The file is a simple shell-compatible environment file using `KEY="VALUE"` format. It must be kept private and not committed to source control with real values.

# Goal
The prompt file captures the required configuration fields for S3 integration.
