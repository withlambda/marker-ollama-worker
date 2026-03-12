# `config/s3-api/aws-commands.sh`

## Context
This script provides a set of convenience functions for interacting with an S3-compatible storage service (like AWS S3 or MinIO) using the AWS CLI. It is intended to be sourced by other scripts.

## Logic
1.  **Configuration Loading**:
    *   `_s3_runpod_set_target_base()`: Loads `s3-config.private.env`, checks for `BUCKET_NAME`, and sets `TARGET_BASE`.
2.  **Base Function**:
    *   `s3_runpod_base()`: Sources `aws-credentials.private.env` and `s3-config.private.env`, exports AWS credentials, and executes `aws --endpoint-url ... s3 ...` in a subshell to avoid leaking credentials.
3.  **Convenience Functions**:
    *   `s3_runpod_cp_file(source, dest)`: Copies a single file to S3.
    *   `s3_runpod_cp_dir(source, dest)`: Recursively copies a directory to S3.
    *   `s3_runpod_sync_upload(source, dest)`: Syncs a local directory *to* S3.
    *   `s3_runpod_sync_download(source, dest)`: Syncs an S3 directory *to* local.
    *   `s3_runpod_delete_file(target)`: Deletes a file from S3.
    *   `s3_runpod_delete_dir(target)`: Recursively deletes a directory from S3.
    *   `s3_runpod_mv_file(source, dest)`: Moves/Renames a file in S3.
    *   `s3_runpod_mv_dir(source, dest)`: Moves/Renames a directory in S3.
    *   `s3_runpod_ls(args)`: Lists S3 contents.

## Dependencies
*   `aws` CLI
*   `aws-credentials.private.env` (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
*   `s3-config.private.env` (ENDPOINT_URL, REGION, BUCKET_NAME)
