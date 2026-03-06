#!/bin/bash

set -e

get_parent_dir() {
  dirname -- "${1}"
}

hf_download() {
  hf download "${1}"
}

process_list_file() {
    local local_cmd=""
    local local_file=""
    local OPTIND=1

    # Parse options
    while getopts "c:f:" opt; do
        case "$opt" in
            c) local_cmd="$OPTARG" ;;
            f) local_file="$OPTARG" ;;
            *) return 1 ;;
        esac
    done

    # Validation
    if [ -z "$local_cmd" ] || [ -z "$local_file" ]; then
        echo "Usage: process_list_file -c <command_name> -f <file_path>" >&2
        return 1
    fi

    if [ -f "$local_file" ]; then
        while IFS= read -r item || [ -n "$item" ]; do
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
