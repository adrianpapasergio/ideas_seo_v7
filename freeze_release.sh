#!/usr/bin/env bash
set -euo pipefail

# ========= Config por defecto =========
REMOTE="${REMOTE:-origin}"
BRANCH="${BRANCH:-main}"
GITHUB_USER="${GITHUB_USER:-adrianpapasergio}"
REPO_NAME="${REPO_NAME:-ideas_seo_v7}"
REMOTE_URL="https://github.com/${GITHUB_USER}/${REPO_NAME}.git"

# ========= Parámetros =========
# Uso:
#   ./freeze_release.sh            # tag auto con fecha y msg por defecto
#   ./freeze_release.sh v1.0.0     # tag explícito
#   ./freeze_release.sh v1.0.1 "Corrección CSV"
TAG="${1:-}"
MSG="${2:-}"

# Si no pasan tag, generamos uno por fecha
if [[ -z "$TAG" ]]; then
  TAG="v$(date +%Y.%m.%d-%H%M)"
fi

# Mensaje por defecto si no se pasa
if [[ -z "$MSG" ]]; then
  MSG="Release estable ${TAG}"
fi

# ========= Verificaciones básicas =========
# 1) Debe ser repo git
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "❌ No estás dentro de un repositorio Git."
  exit 1
fi

# 2) Asegurar rama principal
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$CURRENT_BRANCH" != "$BRANCH" ]]; then
  echo "• Cambiando a rama ${BRANCH} (estabas en ${CURRENT_BRANCH})…"
  git checkout "$BRANCH" 2>/dev/null || git switch "$BRANCH"
fi

# 3) Remoto origin idempotente
if git remote get-url "$REMOTE" >/dev/null 2>&1; then
  # Actualizar URL si difiere
  EXISTING_URL="$(git remote get-url "$REMOTE")"
  if [[ "$EXISTING_URL" != "$REMOTE_URL" ]]; then
    echo "• Actualizando URL de remoto ${REMOTE} -> ${REMOTE_URL}"
    git remote set-url "$REMOTE" "$REMOTE_URL"
  fi
else
  echo "• Agregando remoto ${REMOTE} -> ${REMOTE_URL}"
  git remote add "$REMOTE" "$REMOTE_URL"
fi

# 4) Traer últimos cambios del remoto (idempotente)
echo "• Sincronizando con remoto (${REMOTE}/${BRANCH})…"
git fetch "$REMOTE" "$BRANCH" || true
git pull --rebase "$REMOTE" "$BRANCH" || true

# ========= Commit si hay cambios =========
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "• Hay cambios sin commitear: agregando y creando commit…"
  git add -A
  git commit -m "Release: ${TAG} — ${MSG}"
else
  echo "• No hay cambios locales; usando HEAD actual para la versión."
fi

# ========= Crear/actualizar RELEASES.md (opcional, pero útil) =========
AUTHOR_NAME="$(git config user.name || echo 'Autor')"
NOW_ISO="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
{
  echo "## ${TAG} – ${NOW_ISO}"
  echo "- ${MSG} (por ${AUTHOR_NAME})"
  echo
} >> RELEASES.md

# Añadimos el archivo si es nuevo
git add RELEASES.md
if ! git diff --cached --quiet; then
  git commit -m "Chore: agregar entrada de ${TAG} en RELEASES.md"
fi

# ========= Tag de versión (con protección) =========
if git rev-parse -q --verify "refs/tags/${TAG}" >/dev/null; then
  echo "❌ El tag ${TAG} ya existe. Si querés reetiquetar, borrá y recreá:"
  echo "   git tag -d ${TAG} && git push ${REMOTE} :refs/tags/${TAG}"
  echo "   (luego volvé a correr este script)"
  exit 1
fi

echo "• Creando tag anotado ${TAG}…"
git tag -a "${TAG}" -m "Frozen release: ${MSG}"

# ========= Push branch y tag =========
echo "• Pushing rama ${BRANCH}…"
git push "$REMOTE" "$BRANCH"

echo "• Pushing tag ${TAG}…"
git push "$REMOTE" "${TAG}"

echo "✅ Listo. Versión congelada: ${TAG}"
echo "   Podés ver el historial en RELEASES.md"