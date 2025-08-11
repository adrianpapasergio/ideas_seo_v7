#!/usr/bin/env bash
set -euo pipefail

# ==== CONFIGURÁ ACÁ ====
GITHUB_USER="adrianpapasergio"
GIT_NAME="Adrian Papasergio"
GIT_EMAIL="adrian@planetcommunities.com"
REPO_NAME="ideas_seo_v7"
DEFAULT_BRANCH="main"
TAG_NAME="v7.1"
TAG_MESSAGE="Versión estable v7.1 – lógica ideas/artículos corregida"
# ========================

REMOTE_URL="https://github.com/${GITHUB_USER}/${REPO_NAME}.git"

echo "==> Iniciando en $(pwd)"

# 1) .gitignore (no pisa, solo crea si no existe)
if [ ! -f .gitignore ]; then
  cat > .gitignore <<'EOF'
# Entorno virtual / entorno local
venv/
.env

# Compilados / cache de Python
__pycache__/
*.pyc

# Bases locales
*.db
*.sqlite

# Datos de usuario y artefactos locales
data/ideas/
data/uploads/
*.json

# Logs
*.log
EOF
  echo "✓ .gitignore creado"
else
  echo "• .gitignore ya existe (no modificado)"
fi

# 2) git init (si hace falta)
if [ ! -d .git ]; then
  git init
  echo "✓ Repo Git inicializado"
else
  echo "• Repo Git ya inicializado"
fi

# 3) Config identidad (solo para este repo)
git config user.name  "$GIT_NAME"
git config user.email "$GIT_EMAIL"
echo "✓ Config de usuario para este repo: $GIT_NAME <$GIT_EMAIL>"

# 4) Rama por defecto
git checkout -B "$DEFAULT_BRANCH"

# 5) Primer commit si no hay ninguno
if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
  git add .
  git commit -m "Versión inicial del Generador de Ideas SEO Inteligente"
  echo "✓ Primer commit creado"
else
  echo "• Ya existen commits; agregando cambios si los hay…"
  git add .
  if ! git diff --cached --quiet; then
    git commit -m "Actualización: sincronización previa a publicación"
    echo "✓ Commit de cambios realizado"
  else
    echo "• No hay cambios para commitear"
  fi
fi

# 6) Crear repo remoto automáticamente si tenés GitHub CLI (gh)
if ! git remote get-url origin >/dev/null 2>&1; then
  if command -v gh >/dev/null 2>&1; then
    echo "• Creando repositorio en GitHub con gh…"
    gh repo create "${GITHUB_USER}/${REPO_NAME}" --source . --private --remote origin --push || {
      echo "⚠️  No se pudo crear con gh (¿ya existe?). Intentando setear remoto…"
      git remote add origin "$REMOTE_URL" || true
    }
  else
    echo "• gh no está instalado. Asegurate de crear el repo en GitHub:"
    echo "   https://github.com/new  (nombre: ${REPO_NAME})"
    echo "• Configurando remoto origin -> $REMOTE_URL"
    git remote add origin "$REMOTE_URL" || true
  fi
else
  echo "• Remoto origin ya existe: $(git remote get-url origin)"
fi

# 7) Push rama principal
git push -u origin "$DEFAULT_BRANCH"
echo "✓ Push a $DEFAULT_BRANCH"

# 8) Tag versión (solo si no existe)
if ! git rev-parse -q --verify "refs/tags/${TAG_NAME}" >/dev/null; then
  git tag -a "$TAG_NAME" -m "$TAG_MESSAGE"
  git push origin "$TAG_NAME"
  echo "✓ Tag ${TAG_NAME} creado y publicado"
else
  echo "• Tag ${TAG_NAME} ya existía (no modificado)"
fi

echo "✅ Listo. Repo: $REMOTE_URL"