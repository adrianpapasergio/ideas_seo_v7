#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Uso: $0 \"mensaje de commit\""
  exit 1
fi

MSG="$1"

echo "📦 Agregando cambios…"
git add .

echo "📝 Commit…"
git commit -m "$MSG"

echo "⬆️  Push a main…"
git push origin main

echo "🏷️  Congelando versión…"
./freeze_release.sh
