# Context
This file, `config/s3-api/aws-credentials.private.env`, contains the S3 API keys for access to the RunPod S3-compatible storage. It is sourced by `aws-commands.sh` for authentication.

# Interface

## Variables
- `AWS_ACCESS_KEY_ID`: The public access key identifier for S3 operations.
- `AWS_SECRET_ACCESS_KEY`: The private secret access key for S3 authentication.

# Logic
The file is a shell-compatible environment file using `KEY="VALUE"` format. It must be kept private and not committed to source control with real values.

# Goal
The prompt file captures the required authentication fields for S3 integration.
