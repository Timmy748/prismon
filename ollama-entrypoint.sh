#!/bin/sh
set -eu

model="${OLLAMA_EMBEDDING_MODEL:-embeddinggemma-2:270m-q8_0-text}"

ollama serve &
server_pid=$!

stop_temporary_server() {
  kill "$server_pid" 2>/dev/null || true
  wait "$server_pid" 2>/dev/null || true
}

trap 'stop_temporary_server; exit 143' TERM
trap 'stop_temporary_server; exit 130' INT

until ollama list >/dev/null 2>&1; do
  if ! kill -0 "$server_pid" 2>/dev/null; then
    wait "$server_pid"
    exit 1
  fi
  sleep 1
done

ollama pull "$model"
stop_temporary_server
trap - TERM INT

exec ollama serve
