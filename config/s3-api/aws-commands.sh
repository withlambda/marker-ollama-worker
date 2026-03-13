#!/bin/bash
# aws-commands.sh - S3 utility functions using AWS CLI.
#
# This script provides a set of wrapper functions for common S3 operations
# (cp, sync, rm, mv, ls) tailored for use with RunPod and custom S3 endpoints.
#
# Copyright (C) 2026 withLambda
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

set -e

# If the script is sourced, we need to use BASH_SOURCE[0] to find the location of this script file.
if [[ -n "${BASH_SOURCE[0]}" ]]; then
    SCRIPT_DIR=$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)
else
    SCRIPT_DIR=$(cd -- "$( dirname -- "$0" )" &> /dev/null && pwd)
fi

# Function to generate an error message when a required path argument is missing.
get_path_error() {
  echo "Path to ${*} must be provided"
}

# Pre-defined error messages for common missing arguments.
ERROR_MSG_NO_SOURCE_FILE=$(get_path_error "source file")
ERROR_MSG_NO_TARGET_FILE=$(get_path_error "target file")
ERROR_MSG_NO_SOURCE_DIR=$(get_path_error "source dir")
ERROR_MSG_NO_TARGET_DIR=$(get_path_error "target dir")

# Internal helper function to load the S3 configuration and set the TARGET_BASE variable.
# This function sources the s3-config.private.env file to get the BUCKET_NAME.
#
# Globals:
#   SCRIPT_DIR: The directory where this script resides.
#   TARGET_BASE: This variable is set by this function (e.g., "s3://my-bucket").
_s3_runpod_set_target_base() {
  . "${SCRIPT_DIR}/s3-config.private.env"
  # Ensure BUCKET_NAME is set after sourcing the file.
  : "${BUCKET_NAME:?BUCKET_NAME must be set in s3-config.private.env}"
  TARGET_BASE="s3://${BUCKET_NAME}"
}

# Base function to execute AWS S3 commands with configured credentials and endpoint.
s3_runpod_base() {
  # Use a subshell (...) to contain the environment variables.
  (
    . "${SCRIPT_DIR}/aws-credentials.private.env"
    . "${SCRIPT_DIR}/s3-config.private.env"

    export AWS_ACCESS_KEY_ID
    export AWS_SECRET_ACCESS_KEY
    export AWS_DEFAULT_REGION="${REGION}"

    aws --endpoint-url "${ENDPOINT_URL}" s3 "${@}"
  )
}

# Copies a single file from the local filesystem to the S3 bucket.
#
# Arguments:
#   1. source_file (string): Path to local source file.
#   2. destination_path (string): Destination path in S3 (optional).
s3_runpod_cp_file() {
  S3_PATH="${2#/}"
  _s3_runpod_set_target_base
  s3_runpod_base cp "${1:?$ERROR_MSG_NO_SOURCE_FILE}" "${TARGET_BASE}/${S3_PATH}"
}

# Recursively copies a directory from the local filesystem to the S3 bucket.
#
# Arguments:
#   1. source_dir (string): Path to local source directory.
#   2. destination_dir (string): Destination directory in S3.
s3_runpod_cp_dir() {
  : "${2:?$ERROR_MSG_NO_TARGET_DIR}"
  S3_PATH="${2#/}"
  _s3_runpod_set_target_base
  s3_runpod_base cp "${1:?$ERROR_MSG_NO_SOURCE_DIR}" "${TARGET_BASE}/${S3_PATH}" --recursive
}

# Syncs a directory from the local filesystem to the S3 bucket.
#
# Arguments:
#   1. source_dir (string): Path to local source directory.
#   2. destination_dir (string): Destination directory in S3 (optional).
s3_runpod_sync_upload() {
  S3_PATH="${2#/}"
  _s3_runpod_set_target_base
  s3_runpod_base sync "${1:?$ERROR_MSG_NO_SOURCE_DIR}" "${TARGET_BASE}/${S3_PATH}"
}

# Syncs a directory from the S3 bucket to the local filesystem.
#
# Arguments:
#   1. source_dir (string): Source directory in S3.
#   2. destination_dir (string): Path to local destination directory.
s3_runpod_sync_download() {
  : "${1:?$ERROR_MSG_NO_SOURCE_DIR}"
  # removing leading '/'
  S3_PATH="${1#/}"
  _s3_runpod_set_target_base
  s3_runpod_base sync "${TARGET_BASE}/${S3_PATH}" "${2:?$ERROR_MSG_NO_TARGET_DIR}"
}

# Deletes a single file from the S3 bucket.
#
# Arguments:
#   1. target_file (string): Path to file in S3 to delete.
s3_runpod_delete_file() {
  : "${1:?$ERROR_MSG_NO_TARGET_FILE}"
  S3_PATH="${1#/}"
  _s3_runpod_set_target_base
  s3_runpod_base rm "${TARGET_BASE}/${S3_PATH}"
}

# Recursively deletes a directory from the S3 bucket.
#
# Arguments:
#   1. target_dir (string): Path to directory in S3 to delete.
s3_runpod_delete_dir() {
  : "${1:?$ERROR_MSG_NO_TARGET_DIR}"
  S3_PATH="${1#/}"
  # Ensure trailing slash to correctly identify the directory prefix
  [[ "${S3_PATH}" != */ ]] && S3_PATH="${S3_PATH}/"
  _s3_runpod_set_target_base
  s3_runpod_base rm "${TARGET_BASE}/${S3_PATH}" --recursive
}

# Moves a single file within the S3 bucket.
#
# Arguments:
#   1. source_file (string): Path to source file in S3.
#   2. target_file (string): Path to destination file in S3.
s3_runpod_mv_file() {
  : "${1:?$ERROR_MSG_NO_SOURCE_FILE}"
  : "${2:?$ERROR_MSG_NO_TARGET_FILE}"
  SRC_PATH="${1#/}"
  DEST_PATH="${2#/}"
  _s3_runpod_set_target_base
  s3_runpod_base mv "${TARGET_BASE}/${SRC_PATH}" "${TARGET_BASE}/${DEST_PATH}"
}

# Recursively moves a directory within the S3 bucket.
#
# Arguments:
#   1. source_dir (string): Path to source directory in S3.
#   2. target_dir (string): Path to destination directory in S3.
s3_runpod_mv_dir() {
  : "${1:?$ERROR_MSG_NO_SOURCE_DIR}"
  : "${2:?$ERROR_MSG_NO_TARGET_DIR}"
  SRC_PATH="${1#/}"
  DEST_PATH="${2#/}"
  _s3_runpod_set_target_base
  s3_runpod_base mv "${TARGET_BASE}/${SRC_PATH}" "${TARGET_BASE}/${DEST_PATH}" --recursive
}

# Lists files in the S3 bucket.
#
# Usage:
#   s3_runpod_ls [options]
s3_runpod_ls() {
  _s3_runpod_set_target_base
  s3_runpod_base ls "${TARGET_BASE}" "${@}"
}
