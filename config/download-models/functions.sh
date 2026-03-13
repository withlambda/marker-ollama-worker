#!/bin/bash
# functions.sh - Helper functions for model downloading.
#
# This script contains common utility functions used by the model download
# process, such as Hugging Face CLI wrappers and file list processing.
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

# Returns the parent directory of a given path.
#
# Arguments:
#   1. path (string): The path for which to find the parent directory.
get_parent_dir() {
  dirname -- "${1}"
}

# Wrapper for the Hugging Face download CLI. Tries `hf` first, then `huggingface-cli`.
#
# Arguments:
#   1. model_id (string): The ID of the Hugging Face model to download.
hf_download() {
  if command -v hf >/dev/null 2>&1; then
    hf download "${1}"
  elif command -v huggingface-cli >/dev/null 2>&1; then
    huggingface-cli download "${1}"
  else
    echo "Error: Neither 'hf' nor 'huggingface-cli' is installed or in PATH." >&2
    return 127
  fi
}

# Processes a file line by line, executing a specified command for each line.
#
# Usage:
#   process_list_file -c <command_name> -f <file_path>
#
# Options:
#   -c command_name: The name of the function or command to execute for each item.
#   -f file_path: The path to the file containing the list of items.
#
# Returns:
#   0 on success.
#   1 on error (e.g., missing arguments, file not found).
process_list_file() {
    local local_cmd=""
    local local_file=""
    local OPTIND=1

    # Parse options
    while getopts "c:f:" opt; do
        case "$opt" in
            c) local_cmd="$OPTARG" ;;
            f) local_file="$OPTARG" ;;
            *)
               echo "Usage: process_list_file -c <command_name> -f <file_path>" >&2
               return 1
               ;;
        esac
    done

    # Validation
    if [ -z "$local_cmd" ] || [ -z "$local_file" ]; then
        echo "Usage: process_list_file -c <command_name> -f <file_path>" >&2
        return 1
    fi

    if [ -f "$local_file" ]; then
        while IFS= read -r item || [ -n "$item" ]; do
            # Trim whitespace
            item=$(echo "$item" | xargs)
            # Skip empty lines and comments
            [ -z "$item" ] && continue
            case "$item" in \#*) continue ;; esac

            # Execute the function name stored in local_cmd
            "$local_cmd" "$item"

        done < "$local_file"
    else
        echo "Error: File '$local_file' not found." >&2
        return 1
    fi
}
