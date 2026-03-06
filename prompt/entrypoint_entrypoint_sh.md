# Generate entrypoint/entrypoint.sh

## Instruction
Generate the file `entrypoint/entrypoint.sh` with the exact content provided below.

## Content
```bash
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

# Exit immediately if a command exits with a non-zero status.
set -e

# Check that required environment variables are available
source base-validation-and-config.sh

source start-ollama-server.sh
source build-ollama-model.sh

source run-handler.sh
```
