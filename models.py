import sqlite3, os

DB_PATH = 'data/usuarios.db'

def obtener_conexion():
    return sqlite3.connect(DB_PATH)

def crear_usuario(nombre, email, password_hash):
    conn = obtener_conexion()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO usuarios (nombre, email, password_hash)
            VALUES (?, ?, ?)
        ''', (nombre, email, password_hash))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Email duplicado
    finally:
        conn.close()

def buscar_usuario_por_email(email):
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute('SELECT id, nombre, email, password_hash FROM usuarios WHERE email = ?', (email,))
    usuario = cursor.fetchone()
    conn.close()
    return usuario

# === CONTADORES HISTÓRICOS ===
# Usamos siempre data/usuarios.db
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'usuarios.db')

def ensure_counter_columns():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA table_info(usuarios)")
        cols = [c[1] for c in cur.fetchall()]
        if 'total_ideas' not in cols:
            cur.execute("ALTER TABLE usuarios ADD COLUMN total_ideas INTEGER DEFAULT 0")
        if 'total_articulos' not in cols:
            cur.execute("ALTER TABLE usuarios ADD COLUMN total_articulos INTEGER DEFAULT 0")
        conn.commit()
    except Exception as e:
        print(f"[WARN] ensure_counter_columns: {e}")
    finally:
        conn.close()

def obtener_totales_usuario(email: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(total_ideas,0), COALESCE(total_articulos,0) FROM usuarios WHERE email = ?", (email,))
    fila = cur.fetchone()
    conn.close()
    if fila:
        return int(fila[0] or 0), int(fila[1] or 0)
    return 0, 0

def incrementar_total_ideas(email: str, cantidad: int):
    if not cantidad:
        return
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE usuarios SET total_ideas = COALESCE(total_ideas,0) + ? WHERE email = ?", (cantidad, email))
    conn.commit()
    conn.close()

def incrementar_total_articulos(email: str, cantidad: int = 1):
    if not cantidad:
        return
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE usuarios SET total_articulos = COALESCE(total_articulos,0) + ? WHERE email = ?", (cantidad, email))
    conn.commit()
    conn.close()
# === FIN CONTADORES HISTÓRICOS ===
