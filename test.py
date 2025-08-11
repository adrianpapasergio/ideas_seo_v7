import sqlite3
conn = sqlite3.connect('data/usuarios.db')
cursor = conn.cursor()
cursor.execute("SELECT id, nombre, email FROM usuarios")
print(cursor.fetchall())
conn.close()
