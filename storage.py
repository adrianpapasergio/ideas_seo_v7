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


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def _extraer_titulo_de_html(html: str) -> str:
    """Intenta extraer H1 o H2; si no, arma un fallback con texto plano."""
    if not html:
        return ""
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.I | re.S) or \
        re.search(r"<h2[^>]*>(.*?)</h2>", html, flags=re.I | re.S)
    if m:
        return unescape(re.sub(r"<.*?>", "", m.group(1))).strip()
    # Fallback: primeras 10 palabras del texto plano
    texto = unescape(re.sub(r"<.*?>", " ", html))
    return " ".join(texto.split()[:10]).strip()


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
    """Guarda JSON a disco con identación y UTF-8."""
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[ERROR] No se pudo guardar JSON {ruta}: {e}")
        return False


def _ensure_article_compat(idea: Dict[str, Any]) -> None:
    """
    Mantiene compatibilidad:
    - Si hay lista 'articulos', poner 'articulo' con el último HTML (ítem 0).
    - Si hay 'articulo' legacy y no hay lista, migrar a lista.
    """
    try:
        if isinstance(idea.get("articulos"), list) and idea["articulos"]:
            idea["articulo"] = idea["articulos"][0].get("html", "")
            return

        if idea.get("articulo") and not idea.get("articulos"):
            html = idea["articulo"]
            if (html or "").strip():
                idea["articulos"] = [{
                    "id": str(int(time.time() * 1000) - 1),
                    "titulo": _extraer_titulo_de_html(html) or idea.get("titulo") or idea.get("keyword") or "",
                    "preview": _preview(html),
                    "html": html,
                    "estado": "borrador",
                    "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                }]
    except Exception as e:
        print(f"[WARN] _ensure_article_compat: {e}")


# ------------------------------------------------------
# API DE IDEAS (JSON POR USUARIO)
# ------------------------------------------------------
def cargar_ideas_usuario(email: str) -> list:
    """
    Carga la lista de ideas del usuario. Normaliza compat:
    - Si hay 'articulos' y NO está 'articulo', setea 'articulo' con el último HTML.
    - Si solo hay 'articulo' (legacy), migra a 'articulos'.
    """
    ruta = _ruta_json_usuario(email)
    ideas = _cargar_json_seguro(ruta)
    changed = False

    for i in ideas:
        before = json.dumps(i, ensure_ascii=False, sort_keys=True)
        _ensure_article_compat(i)
        after = json.dumps(i, ensure_ascii=False, sort_keys=True)
        if before != after:
            changed = True

    if changed:
        _guardar_json_seguro(ruta, ideas)

    return ideas


def _merge_ideas_list(base: List[Dict[str, Any]], nuevas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Fusiona listas de ideas por 'keyword' (case-insensitive).
    - Si la keyword existe, reemplaza la idea completa, pero conserva 'articulos' existentes
      cuando la idea nueva no trae 'articulos'.
    - Si es nueva, se agrega.
    """
    base = base if isinstance(base, list) else []
    nuevas = nuevas if isinstance(nuevas, list) else []

    idx: Dict[str, Dict[str, Any]] = {}
    for it in base:
        if isinstance(it, dict):
            idx[_norm(it.get("keyword"))] = it

    for it in nuevas:
        if not isinstance(it, dict):
            continue
        k = _norm(it.get("keyword"))
        if not k:
            continue

        incoming = dict(it)  # copia
        existing = idx.get(k)

        if existing:
            # Conservar artículos existentes si los nuevos no vienen
            if "articulos" not in incoming or not isinstance(incoming.get("articulos"), list):
                incoming["articulos"] = existing.get("articulos", [])
            # Mantener compatibilidad 'articulo'
            _ensure_article_compat(incoming)
            idx[k] = incoming
        else:
            _ensure_article_compat(incoming)
            idx[k] = incoming

    return list(idx.values())


def guardar_ideas_usuario(email: str, ideas: list) -> None:
    """
    Guarda ideas fusionando por keyword (no sobreescribe a ciegas).
    - Si querés sobreescritura total, usá explícitamente _guardar_json_seguro.
    """
    ruta = _ruta_json_usuario(email)
    actuales = cargar_ideas_usuario(email)
    fusionadas = _merge_ideas_list(actuales, ideas)
    os.makedirs(IDEAS_DIR, exist_ok=True)
    _guardar_json_seguro(ruta, fusionadas)


def eliminar_idea_usuario(email: str, keyword: str) -> bool:
    """
    Elimina una idea del usuario por keyword (case-insensitive).
    No modifica el contador persistente de ideas generadas.
    """
    try:
        ideas = cargar_ideas_usuario(email)
        if not isinstance(ideas, list):
            return False

        norm_kw = (keyword or "").strip().lower()
        nuevas = [i for i in ideas if (i.get("keyword") or "").strip().lower() != norm_kw]

        guardar_ideas_usuario(email, nuevas)
        return True
    except Exception as e:
        print("[storage] eliminar_idea_usuario error:", e)
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
        print(f".[WARN] _ensure_counter_columns: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def incrementar_articulos_generados(email: str) -> None:
    """Incrementa el contador de artículos en usuarios.db (columna articulos_generados)."""
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
    Estructura:
      idea['articulos'] = [ { id, titulo, preview, html, estado?, created_at }, ... ]
    Mantiene compat: idea['articulo'] = último HTML.
    """
    try:
        ruta = _ruta_json_usuario(email)
        ideas = cargar_ideas_usuario(email)

        key_norm = _norm(keyword)
        idea_ref = None
        for i in ideas:
            if _norm(i.get("keyword")) == key_norm:
                idea_ref = i
                break

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

        _ensure_article_compat(idea_ref)

        titulo_final = titulo or _extraer_titulo_de_html(articulo_html) or idea_ref.get("titulo") or keyword
        nuevo = {
            "id": str(int(time.time() * 1000)),
            "titulo": titulo_final,
            "preview": _preview(articulo_html),
            "html": articulo_html or "",
            "estado": "borrador",
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }
        idea_ref.setdefault("articulos", [])
        idea_ref["articulos"].insert(0, nuevo)
        idea_ref["articulo"] = articulo_html or ""

        return _guardar_json_seguro(ruta, ideas)
    except Exception as e:
        print(f"[ERROR] guardar_articulo_usuario: {e}")
        return False


def append_articulo_usuario(email: str, keyword: str, html: str, estado: str = "borrador"):
    """
    Agrega un artículo a la idea indicada (multi-artículo).
    Devuelve el artículo creado.
    """
    try:
        ruta = _ruta_json_usuario(email)
        ideas = cargar_ideas_usuario(email)

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

        _ensure_article_compat(idea)

        articulo = {
            "id": str(uuid.uuid4()),
            "html": html or "",
            "estado": estado or "borrador",
            "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z"
        }
        idea.setdefault("articulos", [])
        idea["articulos"].insert(0, articulo)
        idea["articulo"] = html or ""

        _guardar_json_seguro(ruta, ideas)
        return articulo
    except Exception as e:
        print(f"[ERROR] append_articulo_usuario: {e}")
        return None


# --- Estados de artículos ---
ESTADOS_VALIDOS = {"borrador", "revisado", "publicado", "archivado"}


def update_estado_articulo(email: str, keyword: str, articulo_id: str, estado: str) -> bool:
    """Cambia el estado de un artículo por id dentro de la idea."""
    if not (email and keyword and articulo_id and estado in ESTADOS_VALIDOS):
        return False
    try:
        ruta = _ruta_json_usuario(email)
        ideas = cargar_ideas_usuario(email)
        updated = False

        for idea in ideas:
            if _norm(idea.get("keyword")) != _norm(keyword):
                continue
            arts = idea.get("articulos") or []
            for a in arts:
                if a.get("id") == articulo_id:
                    a["estado"] = estado
                    a["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
                    updated = True
                    break
            break

        if updated:
            return _guardar_json_seguro(ruta, ideas)
        return False
    except Exception as e:
        print(f"[ERROR] update_estado_articulo: {e}")
        return False


def eliminar_articulo_usuario(email: str, keyword: str, articulo_id: str) -> bool:
    """Elimina un artículo individual (por id) dentro de una idea (por keyword)."""
    try:
        ruta = _ruta_json_usuario(email)
        ideas = cargar_ideas_usuario(email)
        changed = False

        for idea in ideas:
            if _norm(idea.get("keyword")) != _norm(keyword):
                continue
            arts = idea.get("articulos") or []
            new_arts = [a for a in arts if a.get("id") != articulo_id]
            if len(new_arts) != len(arts):
                idea["articulos"] = new_arts
                idea["articulo"] = new_arts[0].get("html", "") if new_arts else ""
                changed = True
            break

        return _guardar_json_seguro(ruta, ideas) if changed else False
    except Exception as e:
        print(f"[ERROR] eliminar_articulo_usuario: {e}")
        return False


# ------------------------------------------------------
# IDEAS: API de acumulación
# ------------------------------------------------------
def agregar_ideas_usuario(email: str, nuevas_ideas: list) -> bool:
    """
    Agrega/mergea ideas para el usuario fusionando por 'keyword' (case-insensitive).
    - Si una keyword ya existe, la reemplaza (conserva 'articulos' si la nueva no los trae).
    - Si es nueva, la agrega.
    - Actualiza el contador persistente de ideas solo por las realmente NUEVAS.
    """
    try:
        actuales = cargar_ideas_usuario(email)
        actuales_idx = {_norm(i.get("keyword")): i for i in actuales if isinstance(i, dict)}

        nuevas_ideas = nuevas_ideas if isinstance(nuevas_ideas, list) else []
        nuevas_idx = {}
        nuevas_claves_norm = []

        for idea in nuevas_ideas:
            if not isinstance(idea, dict):
                continue
            k = _norm(idea.get("keyword"))
            if not k:
                continue
            nuevas_idx[k] = idea
            nuevas_claves_norm.append(k)

        # Contar cuántas son realmente nuevas
        realmente_nuevas = [k for k in nuevas_claves_norm if k not in actuales_idx]

        fusionadas = _merge_ideas_list(actuales, list(nuevas_idx.values()))
        guardar_ideas_usuario(email, fusionadas)  # usa merge interno también

        # contador persistente de ideas +N
        try:
            if realmente_nuevas:
                incrementar_ideas_generadas(email, inc=len(realmente_nuevas))
        except Exception:
            pass

        return True
    except Exception as e:
        print("[storage] agregar_ideas_usuario error:", e)
        return False


# --- Setters explícitos para contadores históricos (opcional) ---
def _counters_path() -> str:
    os.makedirs("data", exist_ok=True)
    return os.path.join("data", "counters.json")


def _cargar_contadores() -> Dict[str, Any]:
    p = _counters_path()
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    return {}


def _guardar_contadores(base: Dict[str, Any]) -> None:
    p = _counters_path()
    with open(p, "w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=False, indent=2)


def set_ideas_generadas(email: str, valor: int) -> None:
    base = _cargar_contadores()
    by_user = base.get("by_user", {})
    u = by_user.get(email, {})
    u["ideas_generadas"] = max(0, int(valor))
    by_user[email] = u
    base["by_user"] = by_user
    _guardar_contadores(base)


def set_articulos_generados(email: str, valor: int) -> None:
    base = _cargar_contadores()
    by_user = base.get("by_user", {})
    u = by_user.get(email, {})
    u["articulos_generados"] = max(0, int(valor))
    by_user[email] = u
    base["by_user"] = by_user
    _guardar_contadores(base)