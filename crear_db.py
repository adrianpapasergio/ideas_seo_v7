# crear_db.py
import sqlite3
import os

# Asegurar que el directorio exista
os.makedirs("data", exist_ok=True)

# Ruta donde se guardará la base de datos
conn = sqlite3.connect('data/usuarios.db')
cursor = conn.cursor()

# Crear tabla de usuarios
cursor.execute('''
CREATE TABLE IF NOT EXISTS usuarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  articulos_generados INTEGER DEFAULT 0,
  fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

conn.commit()
conn.close()

print("✅ Base de datos creada correctamente.")
