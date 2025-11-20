#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

to_path() {
  local module="$1"
  echo "${module//./\/}.py"
}

if [ $# -eq 0 ]; then
  poetry run pytest

elif [ $# -eq 1 ]; then
  target="$1"

  if [[ "$target" == *"::"* || "$target" == *.py || "$target" == *"/"* ]]; then
    nodeid="$target"
  else
    nodeid="$(to_path "$target")"
  fi

  poetry run pytest "$nodeid"

else
  module="$1"
  testname="$2"

  module_path="$(to_path "$module")"
  nodeid="${module_path}::${testname}"

  poetry run pytest "$nodeid"
fi
