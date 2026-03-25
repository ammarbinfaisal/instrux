#!/usr/bin/env bash
# instrux: agent instruction scaffolding
#
# usage:
#   ./run.sh init /path/to/project                    # default blocks (parallel-dev, smart-reuse)
#   ./run.sh init /path/to/project --with my-block     # include a custom block too
#   ./run.sh add my-block /path/to/project             # add a block
#   ./run.sh remove my-block /path/to/project          # remove a block
#   ./run.sh list /path/to/project                     # show block status
#
# custom blocks: drop .txt files in ./blocks/ — they become available to all commands.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$SCRIPT_DIR/setup.py" "$@"
