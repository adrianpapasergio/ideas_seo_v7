import os
import json

estructura_esperada = {
    "app.py": False,
    "ideas.py": False,
    "models.py": False,
    "utils.py": False,
    "storage.py": False,
    "crear_db.py": False,
    "templates": ["index.html", "login.html", "registro.html"],
    "static": ["style.css", "logo_scidata.png"],
    "data": {
        "usuarios.db": False,
        "ideas": "carpeta"
    }
}

CLAVES_ESENCIALES = ["keyword", "titulo", "palabras_clave"]

def validar_archivo_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            contenido = json.load(f)
        if not isinstance(contenido, dict):
            return False, "No es un JSON tipo objeto"
        for clave in CLAVES_ESENCIALES:
            if clave not in contenido:
                return False, f"Falta clave: {clave}"
        return True, ""
    except Exception as e:
        return False, f"Error al leer JSON: {e}"

def verificar():
    errores = []
    ideas_ok = False

    for item, contenido in estructura_esperada.items():
        if isinstance(contenido, list):
            if not os.path.isdir(item):
                errores.append(f"❌ Falta carpeta: {item}/")
            else:
                for archivo in contenido:
                    ruta = os.path.join(item, archivo)
                    if not os.path.isfile(ruta):
                        errores.append(f"❌ Falta archivo: {ruta}")
        elif isinstance(contenido, dict):
            if not os.path.isdir(item):
                errores.append(f"❌ Falta carpeta: {item}/")
            else:
                for subitem, tipo in contenido.items():
                    ruta = os.path.join(item, subitem)
                    if tipo == "carpeta":
                        if not os.path.isdir(ruta):
                            errores.append(f"❌ Falta subcarpeta: {ruta}/")
                        else:
                            # Verificar que haya al menos un JSON válido
                            jsons = [f for f in os.listdir(ruta) if f.endswith('.json')]
                            if not jsons:
                                errores.append(f"⚠️ Sin archivos JSON en {ruta}/")
                            else:
                                for jf in jsons:
                                    valido, mensaje = validar_archivo_json(os.path.join(ruta, jf))
                                    if not valido:
                                        errores.append(f"⚠️ JSON inválido: {jf} → {mensaje}")
                                    else:
                                        ideas_ok = True
                    elif tipo is False and not os.path.isfile(ruta):
                        errores.append(f"❌ Falta archivo: {ruta}")
        else:
            if not os.path.isfile(item):
                errores.append(f"❌ Falta archivo: {item}")

    print("\n🔎 Verificación de estructura del proyecto\n")
    if errores:
        for err in errores:
            print(err)
        if ideas_ok:
            print("✅ Se encontró al menos un archivo de idea.json válido.")
    else:
        print("✅ La estructura y los datos del proyecto están correctos.")

if __name__ == "__main__":
    verificar()
