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

import os
from pathlib import Path
from typing import Any

def check_is_dir(path: str) -> None:
    """Checks if the given path is a directory. Raises NotADirectoryError if not."""
    if not os.path.isdir(path):
        raise NotADirectoryError(f"Path '{path}' is not a directory.")

def check_is_not_file(path: str) -> None:
    """Checks if the given path is not a file. Raises ValueError if it is a file."""
    if os.path.isfile(path):
        raise ValueError(f"Path '{path}' is a file.")

def check_no_subdirs(path: str) -> None:
    """Checks if the given directory contains no subdirectories (excluding hidden ones)."""
    subdir_count = sum(1 for entry in os.scandir(path) if entry.is_dir() and not entry.name.startswith('.'))
    if subdir_count > 0:
        raise ValueError(f"Path '{path}' contains subdirectories.")

def is_empty_dir(path: str) -> bool:
    """Checks if the given path is an empty directory (excluding hidden files)."""
    p = Path(path)
    if not p.is_dir():
        return False
    for item in p.iterdir():
        if not item.name.startswith('.'):
            return False
    return True

def check_is_empty_dir(path: str) -> None:
    """Checks if the given path is an empty directory if it exists."""
    if os.path.exists(path) and not is_empty_dir(path):
        raise ValueError(f"Directory '{path}' is not empty.")

class TextProcessor:
    """
    A utility class for processing text inputs, primarily for parsing configuration values.
    """
    @staticmethod
    def to_bool(value: Any) -> bool:
        """
        Parses various input types into a boolean value.

        Args:
            value (Any): The value to parse (str, int, float, or bool).

        Returns:
            bool: The parsed boolean value.

        Raises:
            TypeError: If the input value is not a string, number, or boolean.
            ValueError: If the string/number cannot be unambiguously parsed as a boolean.
        """
        if isinstance(value, bool):
            return value
        if value is None:
            return False

        if not isinstance(value, (str, int, float)):
            raise TypeError(f"Value '{value}' must be string or number, not {type(value)}")

        normalized_value = str(value).lower().strip()
        if not normalized_value:
            return False

        truthy_values = {'true', '1', 'yes', 'on'}
        falsy_values = {'false', '0', 'no', 'off'}

        if normalized_value in truthy_values:
            return True
        if normalized_value in falsy_values:
            return False

        raise ValueError(f"Value '{value}' is not parsable as a boolean.")
