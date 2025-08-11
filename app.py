# -*- coding: utf-8 -*-
import os
import csv
import io
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

# --- módulos propios ---
import storage
import ideas  # generar_ideas_para_keyword, generar_articulo_para_keyword
from models import crear_usuario, buscar_usuario_por_email
from utils import hashear_password, verificar_password

# ------------------------------------------------------
# CONFIG FLASK
# ------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SCIDATA_SECRET", "dev_secret_key")

UPLOAD_FOLDER = os.path.join("data", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ESTADOS_VALIDOS = {"borrador", "revisado", "publicado", "archivado"}

# ------------------------------------------------------
# HELPERS CONTADORES (persistentes con fallback)
# ------------------------------------------------------
def _total_ideas_persistente(email: str, ideas_list: list) -> int:
    """Usa contador persistente si existe; si no, cae a len(ideas_list).
       Si ambos existen, toma el mayor (para no 'bajar' al borrar)."""
    total_json = len(ideas_list or [])
    try:
        persist = storage.obtener_ideas_generadas(email)  # puede no existir
        if isinstance(persist, int):
            return max(persist, total_json)
    except Exception:
        pass
    return total_json


def _total_articulos_persistente(email: str, ideas_list: list) -> int:
    """Cuenta persistente de artículos con fallback a conteo por JSON."""
    fallback = 0
    try:
        fallback = storage.contar_articulos_usuario(email)
    except Exception:
        pass

    try:
        persist = storage.obtener_articulos_generados(email)
        if isinstance(persist, int):
            return max(persist, fallback)
    except Exception:
        pass
    return fallback


def _merge_ideas(existing: list, nuevas: list) -> list:
    """Fusiona por keyword (case-insensitive) sin duplicar."""
    if not isinstance(existing, list):
        existing = []
    if not isinstance(nuevas, list):
        nuevas = []

    norm = lambda s: (s or "").strip().lower()
    vistos = {norm(i.get("keyword")): idx for idx, i in enumerate(existing) if isinstance(i, dict)}

    for item in nuevas:
        if not isinstance(item, dict):
            continue
        k = norm(item.get("keyword"))
        if not k:
            continue
        if k in vistos:
            existing[vistos[k]] = item
        else:
            existing.append(item)
            vistos[k] = len(existing) - 1
    return existing


# ------------------------------------------------------
# AUTH
# ------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = (request.form.get("usuario") or "").strip()
    password = (request.form.get("password") or "")

    usuario = buscar_usuario_por_email(email)  # tupla: (id, nombre, email, password_hash, ...)
    if not usuario:
        return render_template("login.html", error="Credenciales incorrectas")

    try:
        password_hash = usuario[3]
    except Exception:
        return render_template("login.html", error="Usuario mal formado en DB")

    if verificar_password(password, password_hash):
        session["usuario"] = usuario[1]
        session["email"] = usuario[2]
        return redirect(url_for("dashboard"))
    else:
        return render_template("login.html", error="Credenciales incorrectas")


@app.get("/registro")
def registro():
    return render_template("registro.html")


@app.post("/registro")
def registrar():
    nombre = (request.form.get("nombre") or "").strip()
    email = (request.form.get("email") or "").strip()
    password = request.form.get("password") or ""
    if not (nombre and email and password):
        return render_template("registro.html", error="Completá todos los campos")

    password_hash = hashear_password(password)
    if crear_usuario(nombre, email, password_hash):
        return render_template("login.html", registro_exitoso=True)
    else:
        return render_template("registro.html", error="Este email ya está registrado.")


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ------------------------------------------------------
# DASHBOARD
# ------------------------------------------------------
@app.route("/", methods=["GET"])
def root():
    return redirect(url_for("dashboard"))


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "email" not in session:
        return redirect(url_for("login"))

    email = session["email"]
    nombre = session.get("usuario") or "Usuario"

    # --- Manejo de POST del formulario/CSV ---
    if request.method == "POST":
        pais = (request.form.get("pais") or "").strip()
        keyword = (request.form.get("keyword") or "").strip()

        # CSV?
        if "csv" in request.files and request.files["csv"].filename:
            file = request.files["csv"]
            file.stream.seek(0)
            raw = file.read()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("latin-1", errors="ignore")
            wrapper = io.StringIO(text)
            reader = csv.DictReader(wrapper)
            nuevas_ideas = []

            for row in reader:
                kw = (row.get("tendencia") or "").strip()
                pa = (row.get("pais") or pais or "").strip()
                if not kw:
                    continue
                try:
                    nuevas_ideas.extend(
                        ideas.generar_ideas_para_keyword(kw, pa or "Argentina")
                    )
                except Exception as e:
                    print("[WARN] generar_ideas_para_keyword CSV:", e)

            # merge + persistencia + contador (solo ideas NUEVAS)
            try:
                # ✅ merge + persistencia + contador acumulativo
                actuales = storage.cargar_ideas_usuario(email) or []
                fusionadas = _merge_ideas(actuales, nuevas_ideas)
                storage.guardar_ideas_usuario(email, fusionadas)

                # actualizar contador persistente con SOLO las nuevas
                try:
                    nuevas_unicas = len(fusionadas) - len(actuales)
                    if nuevas_unicas > 0:
                        storage.incrementar_ideas_generadas(email, inc=nuevas_unicas)
                except Exception as e:
                    print("[WARN contador ideas CSV]", e)
            except AttributeError:
                # compat si no existiera la función: merge manual y guardar
                current = storage.cargar_ideas_usuario(email)
                merged = _merge_ideas(current, nuevas_ideas)
                storage.guardar_ideas_usuario(email, merged)
                try:
                    storage.incrementar_ideas_generadas(email, inc=len(nuevas_ideas))
                except Exception:
                    pass

            return redirect(url_for("dashboard"))

        # Keyword simple
        if keyword:
            try:
                nuevas_ideas = ideas.generar_ideas_para_keyword(keyword, pais or "Argentina")
            except Exception as e:
                print("[WARN] generar_ideas_para_keyword form:", e)
                nuevas_ideas = []

            try:
                actuales = storage.cargar_ideas_usuario(email) or []
                fusionadas = _merge_ideas(actuales, nuevas_ideas)
                storage.guardar_ideas_usuario(email, fusionadas)

                try:
                    nuevas_unicas = len(fusionadas) - len(actuales)
                    if nuevas_unicas > 0:
                        storage.incrementar_ideas_generadas(email, inc=nuevas_unicas)
                except Exception as e:
                    print("[WARN contador ideas keyword]", e)
            except AttributeError:
                current = storage.cargar_ideas_usuario(email)
                merged = _merge_ideas(current, nuevas_ideas)
                storage.guardar_ideas_usuario(email, merged)
                try:
                    storage.incrementar_ideas_generadas(email, inc=len(nuevas_ideas))
                except Exception:
                    pass

            return redirect(url_for("dashboard"))

        # Sin keyword ni csv -> recargar
        return redirect(url_for("dashboard"))

    # --- GET: render ---
    ideas_list = storage.cargar_ideas_usuario(email)
    total_ideas = _total_ideas_persistente(email, ideas_list)
    total_articulos = _total_articulos_persistente(email, ideas_list)

    return render_template(
        "index.html",
        nombre_usuario=nombre,
        total_ideas=total_ideas,
        total_articulos=total_articulos,
        ideas=ideas_list
    )


# ------------------------------------------------------
# API: contadores (AJAX)
# ------------------------------------------------------
@app.get("/api/counters")
def api_counters():
    if "email" not in session:
        return jsonify(total_ideas=0, total_articulos=0)

    email = session["email"]
    ideas_list = storage.cargar_ideas_usuario(email)

    return jsonify(
        total_ideas=_total_ideas_persistente(email, ideas_list),
        total_articulos=_total_articulos_persistente(email, ideas_list)
    )


# ------------------------------------------------------
# API: generar artículo (AJAX)
#   request: { keyword: "..." }
#   response: { id, html, estado, created_at }
# ------------------------------------------------------
@app.post("/generar-articulo")
def generar_articulo():
    if "email" not in session:
        return jsonify(error="not_authenticated"), 401

    data = request.get_json(silent=True) or {}
    keyword = (data.get("keyword") or "").strip()
    # pais opcional; si querés pasarlo desde el front, ya queda listo
    _pais = (data.get("pais") or "").strip()

    if not keyword:
        return jsonify(error="bad_request"), 400

    try:
        res = ideas.generar_articulo_para_keyword(keyword)
        html = (res or {}).get("html") or ""
    except Exception as e:
        print("[WARN] generar_articulo_para_keyword:", e)
        html = f"<article><h2>{keyword}</h2><p>Contenido generado para «{keyword}».</p></article>"

    email = session["email"]
    articulo = storage.append_articulo_usuario(email, keyword, html, estado="borrador")
    # contador persistente de artículos +1 (no decrece)
    try:
        storage.incrementar_articulos_generados(email)
    except Exception:
        pass

    if not articulo:
        return jsonify(error="persist_error"), 500

    return jsonify({
        "id": articulo["id"],
        "html": articulo["html"],
        "estado": articulo.get("estado", "borrador"),
        "created_at": articulo.get("created_at")
    })


# ------------------------------------------------------
# API: eliminar idea completa (no descuenta totales)
# ------------------------------------------------------
@app.post("/eliminar-idea")
def eliminar_idea():
    if "email" not in session:
        return jsonify(ok=False, error="not_authenticated"), 401

    data = request.get_json(silent=True) or {}
    keyword = (data.get("keyword") or "").strip()
    if not keyword:
        return jsonify(ok=False, error="bad_request"), 400

    ok = storage.eliminar_idea_usuario(session["email"], keyword)
    return jsonify(ok=bool(ok))  # no tocamos contadores persistentes


# ------------------------------------------------------
# API: cambiar estado de un artículo
# ------------------------------------------------------
@app.post("/api/cambiar-estado-articulo")
def api_cambiar_estado_articulo():
    if "email" not in session:
        return jsonify(ok=False, error="not_authenticated"), 401

    data = request.get_json(silent=True) or {}
    keyword = (data.get("keyword") or "").strip()
    articulo_id = (data.get("id") or "").strip()
    estado = (data.get("estado") or "").strip().lower()

    if not (keyword and articulo_id and estado in ESTADOS_VALIDOS):
        return jsonify(ok=False, error="bad_request"), 400

    ok = storage.update_estado_articulo(session["email"], keyword, articulo_id, estado)
    return jsonify(ok=bool(ok))


# ------------------------------------------------------
# API: eliminar artículo individual (no descuenta totales)
# ------------------------------------------------------
@app.post("/api/eliminar_articulo")
def api_eliminar_articulo():
    if "email" not in session:
        return jsonify(ok=False, error="not_authenticated"), 401

    data = request.get_json(silent=True) or {}
    keyword = (data.get("keyword") or "").strip()
    articulo_id = (data.get("id") or "").strip()

    if not (keyword and articulo_id):
        return jsonify(ok=False, error="bad_request"), 400

    ok = storage.eliminar_articulo_usuario(session["email"], keyword, articulo_id)
    return jsonify(ok=bool(ok))  # no tocamos contadores persistentes


# ------------------------------------------------------
# RUN
# ------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # host 127.0.0.1 para no chocar con AirPlay y evitar rebind en :5000 externo
    app.run(host="127.0.0.1", port=port, debug=True)