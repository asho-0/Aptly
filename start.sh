#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -f "${ROOT_DIR}/.env" ]]; then
  cp "${ROOT_DIR}/.env.example" "${ROOT_DIR}/.env"
  echo "Created ${ROOT_DIR}/.env from .env.example"
  echo "Review ${ROOT_DIR}/.env, bot/.env, and extension/.env before re-running."
  exit 1
fi

set -a
source "${ROOT_DIR}/.env"
set +a

BOT_DIR="${ROOT_DIR}/bot"
EXTENSION_DIR="${ROOT_DIR}/extension"
BOT_ENV_FILE="${BOT_ENV_FILE:-${BOT_DIR}/.env}"
EXTENSION_ENV_FILE="${EXTENSION_ENV_FILE:-${EXTENSION_DIR}/.env}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
BUN_BIN="${BUN_BIN:-bun}"
INSTALL_PLAYWRIGHT="${INSTALL_PLAYWRIGHT:-0}"

if [[ ! -f "${BOT_ENV_FILE}" ]]; then
  echo "Missing bot environment file: ${BOT_ENV_FILE}"
  exit 1
fi

if [[ ! -f "${EXTENSION_ENV_FILE}" ]]; then
  echo "Missing extension environment file: ${EXTENSION_ENV_FILE}"
  exit 1
fi

command -v "${PYTHON_BIN}" >/dev/null 2>&1 || { echo "Python not found: ${PYTHON_BIN}"; exit 1; }
command -v "${BUN_BIN}" >/dev/null 2>&1 || { echo "Bun not found: ${BUN_BIN}"; exit 1; }

if [[ ! -d "${BOT_DIR}/.venv" ]]; then
  "${PYTHON_BIN}" -m venv "${BOT_DIR}/.venv"
fi

"${BOT_DIR}/.venv/bin/pip" install --upgrade pip
"${BOT_DIR}/.venv/bin/pip" install -r "${BOT_DIR}/requirements.txt"

if [[ "${INSTALL_PLAYWRIGHT}" == "1" ]]; then
  "${BOT_DIR}/.venv/bin/python" -m playwright install chromium
fi

"${BUN_BIN}" install --cwd "${EXTENSION_DIR}"

(
  cd "${BOT_DIR}"
  .venv/bin/alembic upgrade head
)

cleanup() {
  local code=$?
  trap - EXIT INT TERM
  if [[ -n "${BOT_PID:-}" ]]; then
    kill "${BOT_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${EXT_PID:-}" ]]; then
    kill "${EXT_PID}" >/dev/null 2>&1 || true
  fi
  wait >/dev/null 2>&1 || true
  exit "${code}"
}

trap cleanup EXIT INT TERM

(
  cd "${BOT_DIR}"
  source .venv/bin/activate
  python -m app.main
) &
BOT_PID=$!

(
  cd "${EXTENSION_DIR}"
  "${BUN_BIN}" run dev --host 0.0.0.0
) &
EXT_PID=$!

wait -n "${BOT_PID}" "${EXT_PID}"
