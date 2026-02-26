#!/usr/bin/env bash
set -euo pipefail

# ROOT = carpeta raíz del proyecto (padre de scripts/)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

to_nodeid() {
  local target="$1"

  if [[ "$target" == *"::"* || "$target" == *.py || "$target" == *"/"* ]]; then
    echo "$target"
  else
    echo "${target//./\/}.py"
  fi
}

case $# in
  0)
    echo ">> Ejecutando TODOS los tests"
    poetry run pytest
    ;;

  1)
    nodeid="$(to_nodeid "$1")"
    echo ">> Ejecutando tests en: $nodeid"
    poetry run pytest "$nodeid"
    ;;

  2)
    module_nodeid="$(to_nodeid "$1")"
    nodeid="${module_nodeid}::$2"
    echo ">> Ejecutando test específico: $nodeid"
    poetry run pytest "$nodeid"
    ;;

  *)
    echo "Uso: $0 [modulo] [nombre_test]" >&2
    exit 1
    ;;
esac
