#!/usr/bin/env bash
# smoke_optimize.sh — Smoke test E2E: login → generar idea → generar artículo → optimizar artículo
# Uso rápido:
#   ./smoke_optimize.sh --email USER --password PASS --keyword "Copa Libertadores 2025" --pais Argentina \
#     [--base http://127.0.0.1:5000] [--target https://tu-sitio.test] [--require-online]
#
# Requisitos: bash, curl, jq
set -euo pipefail

# -------------------------
# Defaults + argumentos
# -------------------------
BASE_URL="http://127.0.0.1:5000"
EMAIL=""
PASSWORD=""
KEYWORD=""
PAIS="Argentina"
TARGET_URL=""
REQUIRE_ONLINE="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base) BASE_URL="$2"; shift 2 ;;
    --email) EMAIL="$2"; shift 2 ;;
    --password) PASSWORD="$2"; shift 2 ;;
    --keyword) KEYWORD="$2"; shift 2 ;;
    --pais) PAIS="$2"; shift 2 ;;
    --target) TARGET_URL="$2"; shift 2 ;;
    --require-online) REQUIRE_ONLINE="1"; shift 1 ;;
    -h|--help)
      grep '^# ' "$0" | sed 's/^# //'
      exit 0
      ;;
    *)
      echo "❌ Opción desconocida: $1" >&2
      exit 2
      ;;
  esac
done

# Validaciones mínimas
if [[ -z "$EMAIL" || -z "$PASSWORD" || -z "$KEYWORD" ]]; then
  echo "❌ Faltan argumentos obligatorios. Ver --help" >&2
  exit 2
fi

# Dependencias
for bin in curl jq; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "❌ Falta dependencia: $bin" >&2
    exit 3
  fi
done

# Carpetas temporales
TMP_DIR="$(mktemp -d -t smokeopt-XXXXXX)"
COOKIES="$TMP_DIR/cookies.txt"
OUT="$TMP_DIR/out.json"
HTML_OUT="$TMP_DIR/out.html"
trap 'rm -rf "$TMP_DIR"' EXIT

# -------------------------
# Helpers
# -------------------------
hr() { printf '%*s\n' 60 | tr ' ' '—'; }

expect_json() {
  local body_file="$1"
  local status="$2"
  local ctype="$3"
  if [[ "$ctype" != application/json* ]]; then
    echo "✖ Respuesta no JSON (Content-Type: $ctype, HTTP $status). Cuerpo:" >&2
    cat "$body_file" >&2
    return 1
  fi
  if ! jq empty "$body_file" >/dev/null 2>&1; then
    echo "✖ JSON inválido (HTTP $status). Cuerpo:" >&2
    cat "$body_file" >&2
    return 1
  fi
  return 0
}

curl_json() {
  # curl_json METHOD URL [DATA]
  local method="$1"; shift
  local url="$1"; shift
  local data="${1:-}"

  local http_status ctype
  if [[ -n "$data" ]]; then
    http_status="$(
      curl -sS -X "$method" "$url" \
        -H "Content-Type: application/json" \
        -b "$COOKIES" -c "$COOKIES" \
        --data "$data" \
        -D "$TMP_DIR/hdr" -o "$OUT" ; printf '%s' "$(<"$TMP_DIR/hdr")" | awk 'toupper($1$2)=="HTTP/1.1" {print $2}' | tail -1
    )"
  else
    http_status="$(
      curl -sS -X "$method" "$url" \
        -b "$COOKIES" -c "$COOKIES" \
        -D "$TMP_DIR/hdr" -o "$OUT" ; printf '%s' "$(<"$TMP_DIR/hdr")" | awk 'toupper($1$2)=="HTTP/1.1" {print $2}' | tail -1
    )"
  fi
  ctype="$(awk -F': ' 'tolower($1)=="content-type" {print tolower($2)}' "$TMP_DIR/hdr" | tr -d '\r' | tail -1)"

  expect_json "$OUT" "$http_status" "$ctype"
}

curl_form() {
  # curl_form URL "k1=v1&k2=v2"
  local url="$1"; shift
  local form="$1"; shift
  local http_status ctype
  http_status="$(
    curl -sS -X POST "$url" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -b "$COOKIES" -c "$COOKIES" \
      --data "$form" \
      -D "$TMP_DIR/hdr" -o "$OUT" ; printf '%s' "$(<"$TMP_DIR/hdr")" | awk 'toupper($1$2)=="HTTP/1.1" {print $2}' | tail -1
  )"
  ctype="$(awk -F': ' 'tolower($1)=="content-type" {print tolower($2)}' "$TMP_DIR/hdr" | tr -d '\r' | tail -1)"
  # Este endpoint suele redirigir HTML → ignoramos JSON estricto acá
  return 0
}

# -------------------------
# 0) Diagnóstico (opcional)
# -------------------------
echo "== Verificando /api/diagnostico"
if curl_json "GET" "$BASE_URL/api/diagnostico"; then
  echo "  $(jq -r '. | "openai_enabled: \(.openai_enabled) | model: \(.model) | api_key_present: \(.api_key_present) | mode: \(.mode)"' "$OUT")"
  if [[ "$REQUIRE_ONLINE" == "1" ]]; then
    mode="$(jq -r '.mode // "offline"' "$OUT")"
    if [[ "$mode" != "online" ]]; then
      echo "❌ Se exigía modo online (--require-online) y la app está en: $mode" >&2
      exit 10
    fi
  fi
else
  echo "⚠️ /api/diagnostico no disponible o no JSON. Continúo…" >&2
fi
hr

# -------------------------
# 1) Login
# -------------------------
echo "== Login -> $EMAIL"
curl -sS -X POST "$BASE_URL/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -c "$COOKIES" -b "$COOKIES" \
  --data-urlencode "usuario=$EMAIL" \
  --data-urlencode "password=$PASSWORD" \
  -D "$TMP_DIR/hdr" -o "$HTML_OUT" >/dev/null

# heurística: si redirige a /dashboard o devuelve 200 con HTML del dashboard, lo damos OK
if grep -qi "/dashboard" "$TMP_DIR/hdr"; then
  echo "✔ Login OK (redirect)"
else
  # intentar GET /dashboard para confirmar sesión
  curl -sS "$BASE_URL/dashboard" -b "$COOKIES" -c "$COOKIES" -D "$TMP_DIR/hdr" -o "$HTML_OUT" >/dev/null
  if grep -qi "<title>Generador de Ideas" "$HTML_OUT"; then
    echo "✔ Login OK"
  else
    echo "❌ Login falló. Revisá credenciales / server." >&2
    exit 20
  fi
fi
hr

# -------------------------
# 2) Dashboard (GET simple)
# -------------------------
echo "== Dashboard"
curl -sS "$BASE_URL/dashboard" -b "$COOKIES" -c "$COOKIES" -o "$HTML_OUT" >/dev/null
if grep -qi "<title>Generador de Ideas" "$HTML_OUT"; then
  echo "✔ Dashboard OK -> $HTML_OUT"
else
  echo "❌ No cargó dashboard" >&2
  exit 21
fi
hr

# -------------------------
# 3) Generar ideas via form POST /dashboard
# -------------------------
echo "== Generar ideas para '$KEYWORD' (pais=$PAIS)"
FORM="pais=$(printf %s "$PAIS" | jq -sRr @uri)&keyword=$(printf %s "$KEYWORD" | jq -sRr @uri)"
curl_form "$BASE_URL/dashboard" "$FORM"
# Luego de enviar, el server redirige; traemos dashboard otra vez para verificar
curl -sS "$BASE_URL/dashboard" -b "$COOKIES" -c "$COOKIES" -o "$HTML_OUT" >/dev/null
if grep -q "$KEYWORD" "$HTML_OUT"; then
  title_guess="$(grep -A2 -F "$KEYWORD" "$HTML_OUT" | sed -n 's/.*<h3 class="idea-title">\([^<]*\).*/\1/p' | head -1 || true)"
  echo "✔ Idea presente: $KEYWORD ${title_guess:+– título: $title_guess}"
else
  echo "⚠️ No pude confirmar la idea en el HTML. Continuo con generación de artículo…" >&2
fi
hr

# -------------------------
# 4) Generar artículo (JSON)
# -------------------------
echo "== Generar artículo (JSON) para '$KEYWORD'"
curl_json "POST" "$BASE_URL/generar-articulo" "$(jq -nc --arg k "$KEYWORD" '{keyword:$k}')"
# Validamos estructura y extraemos id/html
if [[ "$(jq -r '.ok // "true"' "$OUT")" != "true" ]]; then
  echo "✖ Respuesta no OK: $(cat "$OUT")" >&2
  exit 30
fi

ART_ID="$(jq -r '.id // empty' "$OUT")"
ART_HTML="$(jq -r '.html // empty' "$OUT")"
if [[ -z "$ART_ID" || -z "$ART_HTML" ]]; then
  echo "✖ Respuesta JSON sin id/html válidos:" >&2
  cat "$OUT" >&2
  exit 31
fi
echo "✔ Artículo generado (id=$ART_ID)"
hr

# -------------------------
# 5) Optimizar artículo (JSON)
# -------------------------
echo "== Optimizar artículo (JSON)"
OPT_PAYLOAD="$(jq -nc \
  --arg html "$ART_HTML" \
  --arg kw "$KEYWORD" \
  --arg tu "$TARGET_URL" \
  '{html:$html, keyword:$kw} + ( $tu|length>0 ? {target_url:$tu} : {} )')"

curl_json "POST" "$BASE_URL/api/optimizar-articulo" "$OPT_PAYLOAD"
if [[ "$(jq -r '.ok // "false"' "$OUT")" != "true" ]]; then
  echo "✖ Optimización no OK: $(cat "$OUT")" >&2
  exit 40
fi
OPT_HTML="$(jq -r '.html // empty' "$OUT")"
if [[ -n "$OPT_HTML" ]]; then
  echo "✔ Optimización OK (HTML recibido)"
else
  echo "⚠️ Optimización OK, pero sin HTML en la respuesta" >&2
fi

# Informe de archivos (si existiera)
FILES_MD="$(jq -r '.files.md // empty' "$OUT")"
FILES_HTML="$(jq -r '.files.html // empty' "$OUT")"
FILES_PDF="$(jq -r '.files.pdf // empty' "$OUT")"
if [[ -n "$FILES_MD$FILES_HTML$FILES_PDF" ]]; then
  echo "→ Archivos:"
  [[ -n "$FILES_MD" ]] && echo "   • MD:   $FILES_MD"
  [[ -n "$FILES_HTML" ]] && echo "   • HTML: $FILES_HTML"
  [[ -n "$FILES_PDF" ]] && echo "   • PDF:  $FILES_PDF"
fi
hr

# -------------------------
# 6) Contadores (opcional)
# -------------------------
if curl_json "GET" "$BASE_URL/api/counters"; then
  echo "== Contadores"
  echo "   Ideas:      $(jq -r '.total_ideas' "$OUT")"
  echo "   Artículos:  $(jq -r '.total_articulos' "$OUT")"
fi

echo "✅ Smoke E2E completado OK"