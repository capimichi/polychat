#!/usr/bin/env bash
set -euo pipefail

ENV_FILE=".env"
FOLDER_NAME="$(basename "$PWD")"
NOTE_NAME="${FOLDER_NAME} .env"

usage() {
  echo "Uso: $0 {up|down}"
  echo "  up   -> carica .env locale su Bitwarden (Secure Note: \"$NOTE_NAME\")"
  echo "  down -> scarica da Bitwarden e scrive .env locale"
}

need() { command -v "$1" >/dev/null 2>&1 || { echo "❌ Serve '$1'"; exit 1; }; }
need bw
need jq

MODE="${1:-}"
[[ "$MODE" == "up" || "$MODE" == "down" ]] || { usage; exit 1; }

# Unlock (riusa BW_SESSION se già presente)
if [[ -z "${BW_SESSION:-}" ]]; then
  echo "🔐 Sblocco Bitwarden..."
  export BW_SESSION="$(bw unlock --raw)"
fi

bw sync >/dev/null

find_existing_id() {
  bw list items --search "$NOTE_NAME" \
    | jq -r --arg n "$NOTE_NAME" '.[] | select(.name==$n and .type==2) | .id' \
    | head -n 1
}

make_secure_note_json() {
  # Converte un item JSON in Secure Note valida
  jq -c --arg name "$NOTE_NAME" --arg notes "$NOTE_CONTENT" '
    .type = 2
    | .name = $name
    | .notes = $notes
    | .secureNote = ( .secureNote // { "type": 0 } )
    | .login = null
    | .card = null
    | .identity = null
    | .sshKey = null
  '
}

EXISTING_ID="$(find_existing_id || true)"

if [[ "$MODE" == "up" ]]; then
  [[ -f "$ENV_FILE" ]] || { echo "❌ '$ENV_FILE' non trovato in $(pwd)"; exit 1; }

  NOTE_CONTENT="$(cat "$ENV_FILE")"

  if [[ -n "${EXISTING_ID:-}" && "${EXISTING_ID:-}" != "null" ]]; then
    echo "✏️  Aggiorno: '$NOTE_NAME' (id: $EXISTING_ID)"

    bw get item "$EXISTING_ID" \
      | make_secure_note_json \
      | bw encode \
      | bw edit item "$EXISTING_ID" >/dev/null

    echo "✅ Nota aggiornata: '$NOTE_NAME'"
  else
    echo "🆕 Creo: '$NOTE_NAME'"

    bw get template item \
      | make_secure_note_json \
      | bw encode \
      | bw create item >/dev/null

    echo "✅ Nota creata: '$NOTE_NAME'"
  fi

elif [[ "$MODE" == "down" ]]; then
  if [[ -z "${EXISTING_ID:-}" || "${EXISTING_ID:-}" == "null" ]]; then
    echo "ℹ️  Nota non trovata su Bitwarden: '$NOTE_NAME' — niente da scaricare."
    exit 0
  fi

  echo "⬇️  Scarico: '$NOTE_NAME' (id: $EXISTING_ID) -> $ENV_FILE"

  # Estrae il campo notes e lo scrive in .env (preserva newline; niente trailing newline extra garantibile al 100% in bash)
  bw get item "$EXISTING_ID" \
    | jq -r '.notes // ""' > "$ENV_FILE"

  echo "✅ File scritto: $(pwd)/$ENV_FILE"
fi
