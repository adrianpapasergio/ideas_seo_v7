#!/usr/bin/env python3
# reset_scidata.py
# Resetea la "base de datos" de archivos JSON y uploads con backup previo.

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR     = PROJECT_ROOT / "data"
USERS_DIR    = DATA_DIR / "users"
UPLOADS_DIR  = DATA_DIR / "uploads"
BACKUP_DIR   = PROJECT_ROOT / "backups"

EMPTY_PAYLOAD = {
    "ideas": [],
    "counters": {"ideas_generadas": 0, "articulos_generados": 0}
}

def backup_users():
    if not USERS_DIR.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup_zip = BACKUP_DIR / f"users_backup_{stamp}.zip"
    shutil.make_archive(backup_zip.with_suffix(""), "zip", USERS_DIR)
    return backup_zip

def clean_uploads():
    if not UPLOADS_DIR.exists():
        return
    for p in UPLOADS_DIR.iterdir():
        try:
            if p.is_file() or p.is_symlink():
                p.unlink(missing_ok=True)
            elif p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
        except Exception as e:
            print(f"[WARN] No pude borrar {p}: {e}")

def hard_reset_users():
    if not USERS_DIR.exists():
        return 0
    count = 0
    for jf in USERS_DIR.glob("*.json"):
        try:
            jf.unlink(missing_ok=True)
            count += 1
        except Exception as e:
            print(f"[WARN] No pude borrar {jf}: {e}")
    return count

def soft_reset_users():
    USERS_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    for jf in USERS_DIR.glob("*.json"):
        try:
            with open(jf, "w", encoding="utf-8") as f:
                json.dump(EMPTY_PAYLOAD, f, ensure_ascii=False, indent=2)
            count += 1
        except Exception as e:
            print(f"[WARN] No pude reescribir {jf}: {e}")
    return count

def main():
    parser = argparse.ArgumentParser(
        description="Reinicia JSON de usuarios y uploads (con backup)."
    )
    parser.add_argument(
        "--mode",
        choices=["hard", "soft"],
        default="hard",
        help="hard: borra JSON; soft: deja JSON con ideas vacías y contadores en 0 (por defecto: hard).",
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="No pedir confirmación interactiva."
    )
    args = parser.parse_args()

    print("Proyecto:", PROJECT_ROOT)
    print("Usuarios:", USERS_DIR)
    print("Uploads :", UPLOADS_DIR)
    print("Modo    :", args.mode)

    if not args.yes:
        ok = input("¿Continuar? Esto no se puede deshacer (s/n): ").strip().lower()
        if ok not in ("s", "si", "sí", "y", "yes"):
            print("Cancelado.")
            sys.exit(0)

    # Backup
    backup_zip = backup_users()
    if backup_zip:
        print(f"[OK] Backup creado: {backup_zip}")

    # Reseteo usuarios
    if args.mode == "hard":
        n = hard_reset_users()
        print(f"[OK] JSON de usuarios eliminados: {n}")
    else:
        n = soft_reset_users()
        print(f"[OK] JSON de usuarios reescritos (vacíos): {n}")

    # Limpieza de uploads
    clean_uploads()
    print("[OK] Carpeta 'data/uploads' limpiada.")

    print("Listo ✅")

if __name__ == "__main__":
    main()