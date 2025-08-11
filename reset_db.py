#!/usr/bin/env python3
# reset_db.py
# Borra todos los registros de la base de datos SQLite

import sqlite3
import os
from pathlib import Path

# Ruta a la base de datos
DB_PATH = Path(__file__).resolve().parent / "data" / "usuarios.db"

def reset_database():
    if not DB_PATH.exists():
        print(f"[WARN] No se encontró la base de datos en: {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        # Obtener todas las tablas
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tablas = [row[0] for row in cur.fetchall()]

        for tabla in tablas:
            if tabla.startswith("sqlite_"):
                continue  # Evitar borrar tablas internas de SQLite
            cur.execute(f"DELETE FROM {tabla};")
            conn.commit()
            print(f"[OK] Registros eliminados de la tabla: {tabla}")

        conn.close()
        print("[OK] Base de datos limpiada con éxito.")

    except Exception as e:
        print(f"[ERROR] No se pudo limpiar la base de datos: {e}")

if __name__ == "__main__":
    confirm = input(f"⚠ Esto borrará TODOS los registros en {DB_PATH}. ¿Confirmar? (s/n): ").strip().lower()
    if confirm in ("s", "si", "sí", "y", "yes"):
        reset_database()
    else:
        print("Cancelado.")