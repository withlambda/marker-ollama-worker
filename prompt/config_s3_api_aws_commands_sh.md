# Context
This file, `config/s3-api/aws-commands.sh`, provides a comprehensive suite of Bash wrapper functions for interacting with S3-compatible storage using the AWS CLI. It is specifically designed to work with custom endpoints (like those provided by RunPod) and automates credential management and path normalization.

# Interface

## Functions

### Core Infrastructure
- `s3_runpod_base(args)`: The base executor. It sources credentials and config, sets environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`), and executes `aws --endpoint-url ... s3`.
- `_s3_runpod_set_target_base()`: Sources `s3-config.private.env` and sets `TARGET_BASE` to `s3://${BUCKET_NAME}`.

### File Operations
- `s3_runpod_cp_file(source, dest)`: Copies a local file to S3.
- `s3_runpod_mv_file(source, dest)`: Moves a file within S3.
- `s3_runpod_delete_file(target)`: Removes a file from S3.

### Directory Operations
- `s3_runpod_cp_dir(source, dest)`: Recursively copies a local directory to S3.
- `s3_runpod_sync_upload(source, dest)`: Syncs a local directory to S3.
- `s3_runpod_sync_download(source, dest)`: Syncs an S3 directory to local.
- `s3_runpod_delete_dir(target)`: Recursively removes a directory from S3.
- `s3_runpod_mv_dir(source, dest)`: Recursively moves a directory within S3.

### Information
- `s3_runpod_ls(options)`: Lists contents of the S3 bucket.

# Logic

### Path Normalization
The script uses `${parameter#/}` to strip leading slashes from S3 paths, ensuring they are treated as relative to the bucket root. For directory deletions, it ensures a trailing slash is present to correctly identify the prefix.

### Credential Isolation
`s3_runpod_base` runs in a subshell `(...)` to ensure that S3-specific environment variables do not leak into the caller's environment.

### Error Handling
Uses `: "${VAR:?MSG}"` to provide clear error messages if required arguments or configuration variables (like `BUCKET_NAME`) are missing.

# Goal
The prompt file provides the full suite of S3 integration logic, including the subshell-based credential management and path normalization rules, enabling the exact regeneration of the S3 utility layer.
