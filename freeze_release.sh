#!/bin/bash
# Congela una versión estable: valida estado, hace pull --rebase y crea un tag anotado.
# Uso:
#   ./freeze_release.sh                # genera versión auto: vYYYY.MM.DD ó vYYYY.MM.DD-2
#   ./freeze_release.sh v2025.08.11    # usa la versión indicada
#   ./freeze_release.sh v2025.08.11 "Mensaje del release"

set -euo pipefail

# --- helpers ---
die() { echo "❌ $*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "No encuentro '$1'. Instálalo y reintentá."
}

in_git_repo() {
  git rev-parse --is-inside-work-tree >/dev/null 2>&1
}

ensure_clean_worktree() {
  # No cambios sin commitear ni index pendiente
  if ! git diff --quiet || ! git diff --cached --quiet; then
    die "Tu árbol de trabajo tiene cambios sin commitear. Hacé commit/stash y reintentá."
  fi
  # No rebase/merge en progreso
  if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ] || [ -f .git/MERGE_HEAD ]; then
    die "Parece haber un rebase/merge en progreso. Terminá/abortá eso y reintentá."
  fi
}

next_auto_version() {
  local base="v$(date +%Y.%m.%d)"
  if ! git rev-parse -q --verify "refs/tags/$base" >/dev/null; then
    echo "$base"
    return 0
  fi
  local n=2
  while git rev-parse -q --verify "refs/tags/${base}-${n}" >/dev/null; do
    n=$((n+1))
  done
  echo "${base}-${n}"
}

# --- prereqs ---
need_cmd git
in_git_repo || die "Ejecutá este script dentro del repo git."
git rev-parse --abbrev-ref HEAD >/dev/null || die "No pude determinar la rama actual."

# --- remoto y rama ---
REMOTE="${REMOTE:-origin}"
BRANCH="${BRANCH:-main}"

git remote get-url "$REMOTE" >/dev/null 2>&1 || die "El remoto '$REMOTE' no existe. Configuralo primero (p.ej. origin)."

# --- validaciones de estado ---
ensure_clean_worktree

# --- sync con remoto ---
echo "⬇️  Fetch desde $REMOTE..."
git fetch "$REMOTE" --tags

# Asegurarnos de estar en main (o la rama configurada)
current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$current_branch" != "$BRANCH" ]; then
  echo "🔀 Cambiando a rama '$BRANCH'..."
  git checkout "$BRANCH"
fi

echo "🔄 Rebase con $REMOTE/$BRANCH..."
git pull --rebase "$REMOTE" "$BRANCH"

# --- determinar versión ---
VERSION="${1:-}"
if [ -z "$VERSION" ]; then
  VERSION="$(next_auto_version)"
fi

# Sanitizar: debe empezar por v y no contener espacios
[[ "$VERSION" =~ ^v[0-9]{4}\.[0-9]{2}\.[0-9]{2}(-[0-9]+)?$ ]] || {
  echo "⚠️  Versión '$VERSION' con formato inesperado."
  echo "    Sugerido: vYYYY.MM.DD o vYYYY.MM.DD-N (ej. v2025.08.11 o v2025.08.11-2)"
}

# Chequear que no exista
if git rev-parse -q --verify "refs/tags/$VERSION" >/dev/null; then
  die "El tag '$VERSION' ya existe. Probá otro (o dejá que el script genere uno automáticamente)."
fi

# --- mensaje del tag ---
TAG_MSG="${2:-}"
if [ -z "$TAG_MSG" ]; then
  read -r -p "📝 Mensaje del release (enter para 'Stable release'): " TAG_MSG || true
  TAG_MSG="${TAG_MSG:-Stable release}"
fi

# --- crear tag y pushear ---
echo "🏷️  Creando tag anotado '$VERSION'..."
git tag -a "$VERSION" -m "$TAG_MSG"

echo "🚀 Pusheando tag a $REMOTE..."
git push "$REMOTE" "$VERSION"

echo "✅ Release congelado:"
echo "   - Rama: $BRANCH"
echo "   - Tag : $VERSION"
echo "   - Msg : $TAG_MSG"