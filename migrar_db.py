# migrar_db.py
import sqlite3

# Ruta a la base de datos
DB_PATH = 'data/usuarios.db'  # Asegurate que la DB esté en esta carpeta o cambiala

def agregar_columna_articulos():
    conn = sqlite3.connect(DB_PATH)  # ✅ Usamos la variable DB_PATH
    cursor = conn.cursor()

    # Verificar si la tabla usuarios existe
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='usuarios'")
    if not cursor.fetchone():
        print("❌ La tabla 'usuarios' no existe en esta base de datos.")
        conn.close()
        return

    # Verificar si la columna ya existe
    cursor.execute("PRAGMA table_info(usuarios)")
    columnas = [col[1] for col in cursor.fetchall()]
    if 'articulos_generados' in columnas:
        print("✅ La columna 'articulos_generados' ya existe.")
    else:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN articulos_generados INTEGER DEFAULT 0")
        print("✅ Columna 'articulos_generados' agregada con valor inicial 0.")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    agregar_columna_articulos()
    
