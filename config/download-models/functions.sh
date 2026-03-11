#!/bin/bash
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
