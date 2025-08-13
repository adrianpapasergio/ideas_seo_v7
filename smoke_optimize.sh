#!/usr/bin/env bash
set -euo pipefail

BASE_URL="http://127.0.0.1:5000"
EMAIL="gustavo@scidata.com.ar"
PASS="Calabria2021!"
KEYWORD="Copa Libertadores 2025"
PAIS="Argentina"

COOKIE_JAR="$(mktemp)"
cleanup() { rm -f "$COOKIE_JAR" >/dev/null 2>&1 || true; }
trap cleanup EXIT

say() { printf "%s\n" "$*"; }
ok()  { printf "✅ %s\n" "$*"; }
err() { printf "❌ %s\n" "$*" >&2; }

# 0) Login (form POST)
say "== Login -> $EMAIL"
LOGIN_RES=$(curl -sS -L -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
  -X POST "$BASE_URL/login" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode "usuario=$EMAIL" \
  --data-urlencode "password=$PASS" \
  -o /dev/null -w "%{http_code}")
if [[ "$LOGIN_RES" != "200" && "$LOGIN_RES" != "302" ]]; then
  err "Login falló (HTTP $LOGIN_RES)"; exit 1
fi
ok "Login OK"

# 1) Dashboard (GET)
say "== Dashboard"
DASH_RES=$(curl -sS -L -c "$COOKIE_JAR" -b "$COOKIE_JAR" -o /dev/null -w "%{http_code}" "$BASE_URL/dashboard")
[[ "$DASH_RES" == "200" ]] || { err "Dashboard falló (HTTP $DASH_RES)"; exit 1; }
ok "Dashboard OK"

# 2) Generar artículo (JSON)
say "== Generar artículo (JSON) para '$KEYWORD'"
GEN_RES=$(curl -sS -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -X POST "$BASE_URL/generar-articulo" \
  -d "$(jq -n --arg kw "$KEYWORD" '{keyword:$kw}')" \
  -w "\n%{http_code}")

HTTP_CODE="${GEN_RES##*$'\n'}"
BODY="${GEN_RES%$'\n'*}"

if [[ "$HTTP_CODE" != "200" ]]; then
  err "HTTP $HTTP_CODE en /generar-articulo"
  echo "$BODY"
  exit 1
fi

# Validar que sea JSON y que ok==true
OK_FLAG=$(jq -r '.ok // false' <<<"$BODY" 2>/dev/null || echo "false")
if [[ "$OK_FLAG" != "true" ]]; then
  err "Respuesta no OK en /generar-articulo"
  echo "$BODY"
  exit 1
fi
ID=$(jq -r '.id'   <<<"$BODY")
HTML=$(jq -r '.html' <<<"$BODY")
[[ -n "$ID" && -n "$HTML" ]] || { err "Faltan campos en respuesta de /generar-articulo"; echo "$BODY"; exit 1; }
ok "Artículo generado (id=$ID)"

# 3) Optimizar artículo (JSON)
say "== Optimizar artículo (JSON)"
OPT_RES=$(curl -sS -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -X POST "$BASE_URL/api/optimizar-articulo" \
  -d "$(jq -n --arg html "$HTML" --arg kw "$KEYWORD" '{html:$html, keyword:$kw}')" \
  -w "\n%{http_code}")

HTTP_CODE="${OPT_RES##*$'\n'}"
BODY="${OPT_RES%$'\n'*}"

if [[ "$HTTP_CODE" != "200" ]]; then
  err "HTTP $HTTP_CODE en /api/optimizar-articulo"
  echo "$BODY"
  exit 1
fi

OK_FLAG=$(jq -r '.ok // false' <<<"$BODY" 2>/dev/null || echo "false")
if [[ "$OK_FLAG" != "true" ]]; then
  err "Respuesta no OK en /api/optimizar-articulo"
  echo "$BODY"
  exit 1
fi

HAS_HTML=$(jq -r 'has("html")' <<<"$BODY")
[[ "$HAS_HTML" == "true" ]] || { err "Optimización sin campo html"; echo "$BODY"; exit 1; }
ok "Optimización OK"
say "== Listo"