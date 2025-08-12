#!/usr/bin/env bash
set -euo pipefail

# ------------------------------
# Helpers
# ------------------------------
die() { echo "❌ $*" >&2; exit 1; }
info(){ echo "➜ $*"; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Comando requerido no encontrado: $1"
}

in_git_repo() {
  git rev-parse --is-inside-work-tree >/dev/null 2>&1
}

is_clean_tree() {
  # árbol limpio == salida vacía
  [[ -z "$(git status --porcelain)" ]]
}

current_branch() {
  git rev-parse --abbrev-ref HEAD
}

remote_url() {
  git remote get-url origin 2>/dev/null || true
}

tag_exists() {
  local tag="$1"
  git rev-parse -q --verify "refs/tags/$tag" >/dev/null 2>&1 && return 0
  git ls-remote --exit-code --tags origin "refs/tags/$tag" >/dev/null 2>&1 && return 0
  return 1
}

validate_tag() {
  local tag="$1"
  # Formato estricto: vYYYY.MM.DD o vYYYY.MM.DD-N
  [[ "$tag" =~ ^v[0-9]{4}\.[0-9]{2}\.[0-9]{2}(-[0-9]+)?$ ]]
}

sanitize_tag() {
  # Reemplaza espacios por guiones y filtra caracteres no válidos
  echo "$1" | tr ' ' '-' | tr -cd '[:alnum:]._-' 
}

# ------------------------------
# Pre-chequeos
# ------------------------------
require_cmd git

in_git_repo || die "No estás dentro de un repositorio Git."
[[ "$(current_branch)" == "main" ]] || die "Parate en 'main' antes de congelar (estás en '$(current_branch)')"

# Rebase pendiente?
if [[ -d .git/rebase-merge || -d .git/rebase-apply ]]; then
  die "Tenés un rebase pendiente. Ejecutá 'git rebase --continue' o '--abort' y reintentá."
fi

# Árbol limpio
if ! is_clean_tree; then
  echo "❌ Tu árbol de trabajo tiene cambios sin commitear."
  echo "   Sugerencias:"
  echo "   - git add -A && git commit -m \"chore: trabajo en curso\""
  echo "   - o bien: git stash push -u -m \"wip\""
  exit 1
fi

# Remoto
REMOTE_URL="$(remote_url)"
[[ -n "$REMOTE_URL" ]] || die "No existe remoto 'origin'. Configuralo con: git remote add origin <url>"

# ------------------------------
# Sync con remoto
# ------------------------------
info "Fetch desde origin…"
git fetch origin

info "Rebase con origin/main…"
git rebase origin/main

# ------------------------------
# Tag + mensaje
# ------------------------------
TAG_INPUT="${1:-}"
MSG_INPUT="${2:-}"

if [[ -z "$TAG_INPUT" ]]; then
  read -r -p "📌 Ingresá versión (formato vYYYY.MM.DD o vYYYY.MM.DD-N): " TAG_INPUT
fi

TAG_INPUT="$(sanitize_tag "$TAG_INPUT")"
validate_tag "$TAG_INPUT" || die "Tag inválido: '$TAG_INPUT'. Usá, por ejemplo: v2025.08.12 o v2025.08.12-1"

tag_exists "$TAG_INPUT" && die "El tag '$TAG_INPUT' ya existe (local o remoto). Elegí otro."

if [[ -z "$MSG_INPUT" ]]; then
  read -r -p "📝 Mensaje del release (ej. 'Versión estable post-fix CSV y contadores'): " MSG_INPUT
  [[ -n "$MSG_INPUT" ]] || MSG_INPUT="Stable release"
fi

# ------------------------------
# RELEASES.md
# ------------------------------
DATE_ISO="$(date -u +"%Y-%m-%d %H:%M:%SZ")"
{
  echo ""
  echo "## $TAG_INPUT — $DATE_ISO"
  echo ""
  echo "- $MSG_INPUT"
} >> RELEASES.md

git add RELEASES.md
git commit -m "chore(release): $TAG_INPUT – $MSG_INPUT" >/dev/null || true

# ------------------------------
# Crear tag y pushear
# ------------------------------
info "Creando tag '$TAG_INPUT'…"
git tag -a "$TAG_INPUT" -m "$MSG_INPUT"

info "Pusheando main + tags a origin…"
git push origin main
git push origin "$TAG_INPUT"

echo "✅ Release congelado como tag: $TAG_INPUT"