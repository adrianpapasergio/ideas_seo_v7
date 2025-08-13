# -*- coding: utf-8 -*-
import os
import json
import re
import time
import sqlite3
import uuid
from typing import Optional, List, Dict, Any
from html import unescape
from datetime import datetime, timezone

# ------------------------------------------------------
# RUTAS / CONSTANTES
# ------------------------------------------------------
IDEAS_DIR = os.path.join("data", "ideas")
DB_PATH = os.path.join("data", "usuarios.db")

os.makedirs(IDEAS_DIR, exist_ok=True)

# ------------------------------------------------------
# HELPERS
# ------------------------------------------------------
def _ruta_json_usuario(email: str) -> str:
    """Devuelve la ruta del JSON de ideas del usuario."""
    safe = (email or "").replace("@", "_at_")
    return os.path.join(IDEAS_DIR, f"{safe}.json")


def _extraer_titulo_de_html(html: str) -> str:
    """Intenta extraer H1 o H2; si no, arma un fallback con texto plano."""
    if not html:
        return ""
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.I | re.S) or \
        re.search(r"<h2[^>]*>(.*?)</h2>", html, flags=re.I | re.S)
    if m:
        return unescape(re.sub(r"<.*?>", "", m.group(1))).strip()
    texto = unescape(re.sub(r"<.*?>", " ", html))
    palabras = texto.split()
    return " ".join(palabras[:12]).strip()


def _preview(html: str, n: int = 140) -> str:
    """Devuelve un resumen plano (sin HTML) de n caracteres."""
    if not html:
        return ""
    texto = unescape(re.sub(r"<.*?>", " ", html)).strip()
    return (texto[:n] + "…") if len(texto) > n else texto


def _cargar_json_seguro(ruta: str):
    """Carga JSON de disco; si no existe o hay error, devuelve lista vacía."""
    if not os.path.exists(ruta):
        return []
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[WARN] No se pudo cargar JSON {ruta}: {e}")
        return []


def _guardar_json_seguro(ruta: str, data) -> bool:
    """Guarda JSON a disco con indentación y UTF-8."""
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[ERROR] No se pudo guardar JSON {ruta}: {e}")
        return False


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


# ------------------------------------------------------
# API DE IDEAS (JSON POR USUARIO)
# ------------------------------------------------------
def guardar_ideas_usuario(email: str, ideas: list) -> None:
    """Sobrescribe el archivo de ideas del usuario con la lista dada."""
    ruta = _ruta_json_usuario(email)
    if not isinstance(ideas, list):
        ideas = []
    os.makedirs(IDEAS_DIR, exist_ok=True)
    _guardar_json_seguro(ruta, ideas)


def cargar_ideas_usuario(email: str) -> list:
    """
    Carga la lista de ideas del usuario. Normaliza compat:
    - Si hay 'articulos' y NO está 'articulo', setea 'articulo' con el último HTML.
    """
    ruta = _ruta_json_usuario(email)
    ideas = _cargar_json_seguro(ruta)

    # Normalización de compatibilidad (articulo <- último de articulos)
    changed = False
    for i in ideas:
        try:
            articulos = i.get("articulos")
            if isinstance(articulos, list) and articulos and not i.get("articulo"):
                for item in reversed(articulos):
                    html = (item or {}).get("html") or ""
                    if html.strip():
                        i["articulo"] = html
                        changed = True
                        break
        except Exception as e:
            print(f"[WARN] Normalización ideas falló en una entrada: {e}")

    if changed:
        _guardar_json_seguro(ruta, ideas)

    return ideas


def eliminar_idea_usuario(email: str, keyword: str) -> bool:
    """Elimina una idea por keyword exacta (match por .get('keyword'))."""
    ruta = _ruta_json_usuario(email)
    if not os.path.exists(ruta):
        return False

    try:
        ideas = _cargar_json_seguro(ruta)
        nuevas_ideas = [i for i in ideas if i.get("keyword") != keyword]
        ok = _guardar_json_seguro(ruta, nuevas_ideas)
        return ok
    except Exception as e:
        print(f"[ERROR] eliminar_idea_usuario: {e}")
        return False


def contar_articulos_usuario(email: str) -> int:
    """
    Cuenta artículos escritos para el usuario:
    - Si existe lista 'articulos', cuenta items con 'html' no vacío.
    - Si no, usa el campo legacy 'articulo' (1 si existe y no está vacío).
    """
    ruta = _ruta_json_usuario(email)
    ideas = _cargar_json_seguro(ruta)
    total = 0
    try:
        for i in ideas:
            if isinstance(i.get("articulos"), list):
                total += sum(1 for a in i["articulos"] if a and (a.get("html") or "").strip())
            else:
                if (i.get("articulo") or "").strip():
                    total += 1
    except Exception as e:
        print(f"[WARN] contar_articulos_usuario: {e}")
    return total


# ------------------------------------------------------
# CONTADORES EN DB (SQLite)
# ------------------------------------------------------
def _ensure_counter_columns():
    """Crea columnas de contadores si no existen (idempotente)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        try:
            cur.execute("ALTER TABLE usuarios ADD COLUMN ideas_generadas INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE usuarios ADD COLUMN articulos_generados INTEGER DEFAULT 0")
        except Exception:
            pass
        conn.commit()
    except Exception as e:
        print(f"[WARN] _ensure_counter_columns: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def incrementar_articulos_generados(email: str) -> None:
    """Incrementa el contador de artículos en usuarios.db (no decrece)."""
    _ensure_counter_columns()
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT articulos_generados FROM usuarios WHERE email = ?", (email,))
        row = cur.fetchone()
        if row is not None:
            nuevo = (row[0] or 0) + 1
            cur.execute("UPDATE usuarios SET articulos_generados = ? WHERE email = ?", (nuevo, email))
            conn.commit()
    except Exception as e:
        print(f"[ERROR] incrementar_articulos_generados: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def obtener_articulos_generados(email: str) -> int:
    """Obtiene el contador de artículos generados desde usuarios.db."""
    _ensure_counter_columns()
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT articulos_generados FROM usuarios WHERE email = ?", (email,))
        row = cur.fetchone()
        return row[0] if row else 0
    except Exception as e:
        print(f"[ERROR] obtener_articulos_generados: {e}")
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def incrementar_ideas_generadas(email: str, inc: int = 1) -> None:
    """Suma inc al contador persistente de ideas (no decrece)."""
    if inc <= 0:
        return
    _ensure_counter_columns()
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT ideas_generadas FROM usuarios WHERE email = ?", (email,))
        row = cur.fetchone()
        if row is not None:
            nuevo = max(0, (row[0] or 0)) + int(inc)
            cur.execute("UPDATE usuarios SET ideas_generadas = ? WHERE email = ?", (nuevo, email))
            conn.commit()
    except Exception as e:
        print(f"[ERROR] incrementar_ideas_generadas: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def obtener_ideas_generadas(email: str) -> int:
    """Devuelve el contador persistente de ideas (0 si no existe)."""
    _ensure_counter_columns()
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT ideas_generadas FROM usuarios WHERE email = ?", (email,))
        row = cur.fetchone()
        return max(0, int(row[0])) if row and row[0] is not None else 0
    except Exception as e:
        print(f"[ERROR] obtener_ideas_generadas: {e}")
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ------------------------------------------------------
# ARTÍCULOS POR IDEA (MÚLTIPLES + COMPAT LEGACY)
# ------------------------------------------------------
def guardar_articulo_usuario(email: str, keyword: str, articulo_html: str, titulo: Optional[str] = None) -> bool:
    """
    Agrega un nuevo artículo a la idea con 'keyword'.

    Nuevo formato:
      idea['articulos'] = [ { id, titulo, preview, html, created_at, estado }, ... ]

    Compatibilidad:
      idea['articulo'] SIEMPRE se actualiza con el **último** HTML para que
      el frontend actual (que lee 'idea.articulo') siga funcionando.
    """
    try:
        ruta = _ruta_json_usuario(email)
        ideas = _cargar_json_seguro(ruta)

        key_norm = _norm(keyword)
        idea_ref = None
        for i in ideas:
            if _norm(i.get("keyword")) == key_norm:
                idea_ref = i
                break

        # Crear idea mínima si no existe
        if idea_ref is None:
            idea_ref = {
                "keyword": keyword,
                "titulo": titulo or keyword,
                "palabras_clave": [],
                "h2_sugeridos": [],
                "tips_seo": [],
                "articulos": []
            }
            ideas.append(idea_ref)

        # Asegurar lista
        if "articulos" not in idea_ref or not isinstance(idea_ref["articulos"], list):
            legacy_html = idea_ref.get("articulo")
            idea_ref["articulos"] = []
            if legacy_html and str(legacy_html).strip():
                idea_ref["articulos"].append({
                    "id": str(int(time.time() * 1000) - 1),
                    "titulo": _extraer_titulo_de_html(legacy_html) or idea_ref.get("titulo") or keyword,
                    "preview": _preview(legacy_html),
                    "html": legacy_html,
                    "estado": "borrador",
                    "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                })

        # Agregar el nuevo artículo
        titulo_final = titulo or _extraer_titulo_de_html(articulo_html) or idea_ref.get("titulo") or keyword
        nuevo = {
            "id": str(int(time.time() * 1000)),
            "titulo": titulo_final,
            "preview": _preview(articulo_html),
            "html": articulo_html or "",
            "estado": "borrador",
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }
        idea_ref["articulos"].append(nuevo)

        # Compat: mantener 'articulo' con el ÚLTIMO HTML
        idea_ref["articulo"] = articulo_html or ""

        ok = _guardar_json_seguro(ruta, ideas)
        if not ok:
            return False

        return True
    except Exception as e:
        print(f"[ERROR] guardar_articulo_usuario: {e}")
        return False


def append_articulo_usuario(email: str, keyword: str, html: str, estado: str = "borrador") -> Optional[Dict[str, Any]]:
    """
    Agrega un artículo a la idea indicada (multi-artículo) y lo inserta arriba.
    Mantiene compatibilidad actualizando idea['articulo'] con el último HTML.
    """
    try:
        ruta = _ruta_json_usuario(email)
        ideas = _cargar_json_seguro(ruta)

        # Buscar idea
        idea = None
        for i in ideas:
            if _norm(i.get("keyword")) == _norm(keyword):
                idea = i
                break

        if not idea:
            idea = {
                "keyword": keyword,
                "titulo": keyword,
                "palabras_clave": [],
                "h2_sugeridos": [],
                "tips_seo": [],
                "articulos": []
            }
            ideas.append(idea)

        if "articulos" not in idea or not isinstance(idea["articulos"], list):
            legacy_html = idea.pop("articulo", None)
            idea["articulos"] = []
            if legacy_html and str(legacy_html).strip():
                idea["articulos"].append({
                    "id": str(uuid.uuid4()),
                    "html": legacy_html,
                    "estado": "borrador",
                    "titulo": _extraer_titulo_de_html(legacy_html) or idea.get("titulo") or keyword,
                    "preview": _preview(legacy_html),
                    "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z"
                })

        articulo = {
            "id": str(uuid.uuid4()),
            "html": html or "",
            "estado": estado or "borrador",
            "titulo": _extraer_titulo_de_html(html) or idea.get("titulo") or keyword,
            "preview": _preview(html),
            "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z"
        }
        # Insertar al principio
        idea["articulos"].insert(0, articulo)

        # Compat: actualizar 'articulo'
        idea["articulo"] = html or ""

        _guardar_json_seguro(ruta, ideas)
        return articulo
    except Exception as e:
        print(f"[ERROR] append_articulo_usuario: {e}")
        return None


# --- Estados de artículos ---
ESTADOS_VALIDOS = {"borrador", "revisado", "publicado", "archivado"}


def update_estado_articulo(email: str, keyword: str, articulo_id: str, estado: str) -> bool:
    """
    Cambia el estado de un artículo (por id) dentro de la idea (por keyword) del usuario (email).
    Persiste en data/ideas/<email>.json. Devuelve True si se guardó bien.
    """
    if not (email and keyword and articulo_id and estado in ESTADOS_VALIDOS):
        return False

    try:
        ruta = _ruta_json_usuario(email)
        if not os.path.exists(ruta):
            return False

        ideas = _cargar_json_seguro(ruta)
        updated = False
        for idea in ideas:
            if _norm(idea.get("keyword")) != _norm(keyword):
                continue

            # Soporte legacy: mover 'articulo' único a 'articulos'
            if idea.get("articulo") and not idea.get("articulos"):
                idea["articulos"] = [{
                    "id": "legacy",
                    "html": idea["articulo"],
                    "estado": "borrador",
                    "created_at": None,
                }]
                idea.pop("articulo", None)

            arts = idea.get("articulos") or []
            for a in arts:
                if a.get("id") == articulo_id:
                    a["estado"] = estado
                    a["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
                    updated = True
                    break
            break

        if updated:
            _guardar_json_seguro(ruta, ideas)

        return updated
    except Exception as e:
        print(f"[ERROR] update_estado_articulo: {e}")
        return False


def eliminar_articulo_usuario(email: str, keyword: str, articulo_id: str) -> bool:
    """
    Elimina un artículo individual (por id) dentro de una idea (por keyword).
    No modifica contadores persistentes.
    """
    try:
        ruta = _ruta_json_usuario(email)
        if not os.path.exists(ruta):
            return False

        ideas = _cargar_json_seguro(ruta)
        changed = False
        for idea in ideas:
            if _norm(idea.get("keyword")) != _norm(keyword):
                continue
            arts = idea.get("articulos") or []
            new_arts = [a for a in arts if a.get("id") != articulo_id]
            if len(new_arts) != len(arts):
                idea["articulos"] = new_arts
                # mantener compat 'articulo' con el último HTML
                if new_arts:
                    idea["articulo"] = new_arts[0].get("html", "")
                else:
                    idea["articulo"] = ""
                changed = True
            break

        if changed:
            return _guardar_json_seguro(ruta, ideas)
        return False
    except Exception as e:
        print(f"[ERROR] eliminar_articulo_usuario: {e}")
        return False


# ------------------------------------------------------
# MERGE / IMPORTACIÓN DE IDEAS + contador persistente
# ------------------------------------------------------
def agregar_ideas_usuario(email: str, nuevas_ideas: List[Dict[str, Any]]) -> bool:
    """
    Fusiona ideas por 'keyword' (case-insensitive):
    - Si la keyword ya existe, la reemplaza (update).
    - Si es nueva, la agrega.
    - Incrementa el contador persistente de ideas SOLO por las realmente nuevas.
    """
    try:
        if not isinstance(nuevas_ideas, list):
            nuevas_ideas = []

        actuales = cargar_ideas_usuario(email)
        if not isinstance(actuales, list):
            actuales = []

        def norm(s):
            return (s or "").strip().lower()

        idx = {norm(i.get("keyword")): i for i in actuales if isinstance(i, dict)}
        agregadas = 0

        for idea in nuevas_ideas:
            if not isinstance(idea, dict):
                continue
            k = norm(idea.get("keyword"))
            if not k:
                continue
            if k in idx:
                # reemplazar/actualizar
                idx[k] = idea
            else:
                idx[k] = idea
                agregadas += 1

        fusionadas = list(idx.values())
        guardar_ideas_usuario(email, fusionadas)

        # contador persistente de ideas +N (solo nuevas)
        try:
            incrementar_ideas_generadas(email, inc=agregadas)
        except Exception as e:
            print("[WARN] incrementar_ideas_generadas:", e)

        return True
    except Exception as e:
        print("[storage] agregar_ideas_usuario error:", e)
        return False


# ------------------------------------------------------
# Setters explícitos para contadores históricos (opcional)
# ------------------------------------------------------
def set_ideas_generadas(email: str, valor: int) -> None:
    """Fija el contador histórico de ideas para un usuario en usuarios.db."""
    _ensure_counter_columns()
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("UPDATE usuarios SET ideas_generadas = ? WHERE email = ?", (max(0, int(valor)), email))
        conn.commit()
    except Exception as e:
        print(f"[ERROR] set_ideas_generadas: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def set_articulos_generados(email: str, valor: int) -> None:
    """Fija el contador histórico de artículos para un usuario en usuarios.db."""
    _ensure_counter_columns()
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("UPDATE usuarios SET articulos_generados = ? WHERE email = ?", (max(0, int(valor)), email))
        conn.commit()
    except Exception as e:
        print(f"[ERROR] set_articulos_generados: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass