# Configure management of network volumes via S3 API

## Download AWS CLI

1. Download AWS CLI installer to a preferred directory:
```shell
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
```
2. Run installer:
```shell
sudo installer -pkg AWSCLIV2.pkg -target /
```
3. Verify installation
```shell
aws --version
```

## Configure S3 API

Before using the scripts, you must configure your S3 connection details.

1.  Create `config/s3-api/aws-credentials.private.env`:
    ```bash
    export AWS_ACCESS_KEY_ID="your_access_key_id"
    export AWS_SECRET_ACCESS_KEY="your_secret_access_key"
    ```

2.  Create `config/s3-api/s3-config.private.env`:
    ```bash
    export ENDPOINT_URL="https://s3.example.com"
    export REGION="us-east-1"
    export BUCKET_NAME="your-bucket-name"
    ```

**Note:** The `.private.env` files are ignored by git to protect your credentials.

## Shell Script Commands (`aws-commands.sh`)

The `aws-commands.sh` script provides a set of convenience functions for interacting with an S3-compatible storage service (specifically tailored for RunPod or similar S3 providers). It wraps the AWS CLI commands.

**Important**: The functions run `aws` commands in a subshell, so exported environment variables (like `AWS_ACCESS_KEY_ID`) are contained within that command execution and do not leak into your current shell session.

To use these functions in your terminal or scripts, source the file:

```bash
source config/s3-api/aws-commands.sh
```

### Functions

#### `s3_runpod_ls [options]`
Lists S3 objects and common prefixes under a prefix or all S3 buckets.
*   **options**: (Optional) Standard `aws s3 ls` options.

#### `s3_runpod_cp_file <source_file> [destination_path]`
Copies a single file from the local filesystem to the configured S3 bucket.
*   **source_file**: Path to the local file to upload.
*   **destination_path**: (Optional) Destination path within the bucket. If omitted, uploads to the root of the bucket with the same filename.

#### `s3_runpod_cp_dir <source_dir> <destination_dir>`
Recursively copies a local directory to the S3 bucket.
*   **source_dir**: Path to the local directory.
*   **destination_dir**: Destination directory path within the bucket.

#### `s3_runpod_sync_upload <source_dir> [destination_dir]`
Syncs a local directory **to** the S3 bucket (only uploads new or modified files).
*   **source_dir**: Path to the local directory.
*   **destination_dir**: (Optional) Destination directory path within the bucket.

#### `s3_runpod_sync_download <source_dir_in_bucket> <destination_dir>`
Syncs a directory **from** the S3 bucket to the local filesystem (only downloads new or modified files).
*   **source_dir_in_bucket**: Path to the directory in the bucket to download.
*   **destination_dir**: Local destination directory path.

#### `s3_runpod_delete_file <file_path>`
Deletes a single file from the S3 bucket.
*   **file_path**: Path of the file in the bucket to delete.

#### `s3_runpod_delete_dir <dir_path>`
Recursively deletes a directory from the S3 bucket.
*   **dir_path**: Path of the directory in the bucket to delete.

#### `s3_runpod_mv_file <source_path> <destination_path>`
Moves (renames) a file within the S3 bucket (server-side operation).
*   **source_path**: Current path of the file in the bucket.
*   **destination_path**: New path for the file in the bucket.

#### `s3_runpod_mv_dir <source_dir> <destination_dir>`
Recursively moves a directory within the S3 bucket (server-side operation).
*   **source_dir**: Current path of the directory in the bucket.
*   **destination_dir**: New path for the directory in the bucket.
