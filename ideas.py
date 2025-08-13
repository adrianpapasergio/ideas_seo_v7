# -*- coding: utf-8 -*-
import os
import json
import re
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# =========================================================
# Carga de .env y cliente OpenAI opcional
# =========================================================
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()  # podés cambiarlo por gpt-4o
client = None
if OPENAI_API_KEY:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception:
        client = None

# =========================================================
# Helpers internos
# =========================================================
_CODE_FENCE_RE = re.compile(r"^```[\w-]*\s*([\s\S]*?)\s*```$", re.I | re.M)

def _strip_code_fences(text: str) -> str:
    """
    Quita fences tipo ```...``` y devuelve solo el contenido.
    Tolera que venga con o sin 'json' / 'html' declarados.
    """
    if not text:
        return ""
    t = text.strip()
    m = _CODE_FENCE_RE.match(t)
    if m:
        return m.group(1).strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines:
            head = lines[0].strip("`").strip()
            if head == "" or head.isalpha():
                t = "\n".join(lines[1:]).strip()
            if t.endswith("```"):
                t = t[:-3].rstrip()
    return t

def _clean_json_block(s: str) -> str:
    """
    Extrae el primer bloque que parece un array JSON desde la respuesta del modelo.
    """
    if not s:
        return "[]"
    # Quitar code fences
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s.strip(), flags=re.I | re.M)
    # Buscar desde el primer '[' hasta el último ']'
    start = s.find("[")
    end = s.rfind("]")
    if start != -1 and end != -1 and end > start:
        return s[start:end + 1].strip()
    return "[]"

def _md_to_html_minimal(md: str) -> str:
    """
    Conversión mínima de Markdown a HTML para casos en los que el modelo no
    devuelve HTML puro. No pretende ser completa, solo lo esencial.
    """
    if not md:
        return ""
    text = md.strip()

    # Quitar fences de código completos
    text = re.sub(r"^```.*?```", "", text, flags=re.S)

    # Encabezados
    text = re.sub(r"(?m)^\s*###\s+(.*)$", r"<h3>\1</h3>", text)
    text = re.sub(r"(?m)^\s*##\s+(.*)$", r"<h2>\1</h2>", text)
    text = re.sub(r"(?m)^\s*#\s+(.*)$", r"<h1>\1</h1>", text)

    # Quitar **negritas** y *itálicas* simples
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)

    # Bullets simples -> párrafos
    text = re.sub(r"(?m)^\s*-\s+(.*)$", r"<p>\1</p>", text)

    # Separar por líneas vacías y envolver en <p> si no hay etiqueta
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    wrapped = []
    for p in parts:
        if p.startswith("<h") or p.startswith("<p>") or p.startswith("<ul>") or p.startswith("<article>"):
            wrapped.append(p)
        else:
            wrapped.append(f"<p>{p}</p>")

    html = "\n".join(wrapped).strip()
    if "<article" not in html.lower():
        html = f"<article>\n{html}\n</article>"
    return html

def _ensure_article_wrapper(html: str) -> str:
    """
    Asegura que el contenido esté envuelto en <article> ... </article>
    y limpia posibles fences.
    """
    if not html:
        return "<article></article>"
    html = _strip_code_fences(html)
    if re.search(r"<article\b", html, flags=re.I):
        return html
    return f"<article>\n{html}\n</article>"

# =========================================================
# Fallbacks offline
# =========================================================
def _fallback_ideas(keyword: str, pais: Optional[str], n: int = 3) -> List[Dict[str, Any]]:
    """
    Genera ideas sin LLM, para modo offline/errores.
    """
    base = [
        {
            "keyword": f"{keyword} guía {pais or ''}".strip(),
            "titulo": f"Guía completa sobre {keyword}" + (f" en {pais}" if pais else ""),
            "palabras_clave": [keyword, f"{keyword} paso a paso", f"{keyword} requisitos"],
            "h2_sugeridos": [
                f"¿Qué es {keyword}?",
                f"Cómo empezar con {keyword}",
                f"Errores frecuentes con {keyword}",
            ],
            "tips_seo": [
                "Incluí la keyword en el H1 y en el primer párrafo.",
                "Aprovechá preguntas frecuentes con H2/H3.",
            ],
            "articulo": ""
        },
        {
            "keyword": f"{keyword} 2025 {pais or ''}".strip(),
            "titulo": f"Novedades y cambios sobre {keyword} en 2025",
            "palabras_clave": [keyword, f"{keyword} novedades", f"{keyword} 2025"],
            "h2_sugeridos": [
                "Contexto y tendencias",
                "Impacto para usuarios",
                "Recomendaciones prácticas",
            ],
            "tips_seo": [
                "Usá subtítulos descriptivos con intención de búsqueda.",
                "Agregá ejemplos concretos para mejorar el tiempo de lectura.",
            ],
            "articulo": ""
        },
        {
            "keyword": f"{keyword} preguntas frecuentes {pais or ''}".strip(),
            "titulo": f"Preguntas frecuentes sobre {keyword}" + (f" en {pais}" if pais else ""),
            "palabras_clave": [keyword, f"{keyword} faq", f"dudas sobre {keyword}"],
            "h2_sugeridos": [
                f"Preguntas básicas sobre {keyword}",
                f"Casos especiales frecuentes",
                f"Recursos útiles",
            ],
            "tips_seo": [
                "Marcá FAQs con estructura ordenada.",
                "Incluí enlaces internos a artículos relacionados.",
            ],
            "articulo": ""
        },
    ]
    return base[:n]

def _fallback_article(keyword: str) -> str:
    """
    Artículo HTML completo de fallback.
    """
    titulo = f"{keyword.capitalize()}: guía práctica y ejemplos"
    cuerpo = f"""
<h1>{titulo}</h1>
<p>En esta guía vas a encontrar una explicación clara sobre <em>{keyword}</em>, con pasos concretos, ejemplos y recomendaciones para que puedas aplicarlo hoy mismo.</p>

<h2>¿Qué es {keyword}?</h2>
<p>{keyword.capitalize()} es un tema que suele generar dudas. Aquí lo desglosamos de forma simple para que entiendas su alcance y sus implicancias en el día a día.</p>

<h2>Cómo empezar</h2>
<p>1) Definí tu objetivo. 2) Identificá la información necesaria. 3) Seguí un proceso paso a paso. Registrar lo aprendido te ayudará a mejorar los resultados.</p>

<h2>Errores frecuentes</h2>
<p>• No verificar fuentes. • Saltar pasos del procedimiento. • No medir resultados. Evitarlos te ahorrará tiempo y retrabajo.</p>

<h2>Recursos útiles</h2>
<p>Buscá guías oficiales, casos de uso y foros especializados para resolver dudas específicas sobre {keyword}.</p>

<h2>Conclusiones</h2>
<p>Aplicar buenas prácticas alrededor de <em>{keyword}</em> puede marcar la diferencia. Empezá por lo simple y evolucioná tu proceso gradualmente.</p>

<h2>Tips SEO</h2>
<p>Incluí la palabra clave en el título, usá H2 claros con intención de búsqueda y reforzá con ejemplos prácticos.</p>
""".strip()
    return _ensure_article_wrapper(cuerpo)

# =========================================================
# API principal expuesta
# =========================================================
def generar_ideas_para_keyword(keyword: str, pais: Optional[str]) -> List[Dict[str, Any]]:
    """
    Devuelve 3 ideas como lista de dicts con:
      keyword, titulo, palabras_clave[], h2_sugeridos[], tips_seo[], articulo=""
    """
    if not keyword:
        return []

    # Modo offline
    if client is None:
        return _fallback_ideas(keyword, pais, n=3)

    prompt = f"""
Generá 3 ideas de contenido SEO en español para la keyword "{keyword}" orientadas a {pais or "Hispanoamérica"}.
Devolvé EXCLUSIVAMENTE un array JSON válido con la forma:

[
  {{
    "keyword": "...",
    "titulo": "...",
    "palabras_clave": ["...", "..."],
    "h2_sugeridos": ["...", "..."],
    "tips_seo": ["...", "..."],
    "articulo": ""
  }},
  ...
]

- No agregues texto fuera del array JSON.
- "articulo" debe venir SIEMPRE como cadena vacía.
""".strip()

    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Sos un generador de ideas SEO experto."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
        )
        raw = resp.choices[0].message.content.strip()
        cleaned = _clean_json_block(raw)
        ideas = json.loads(cleaned)

        fixed = []
        for it in ideas if isinstance(ideas, list) else []:
            fixed.append({
                "keyword": str(it.get("keyword", keyword)),
                "titulo": (str(it.get("titulo", keyword)) or keyword).strip(),
                "palabras_clave": list(it.get("palabras_clave", [])) if isinstance(it.get("palabras_clave"), list) else [],
                "h2_sugeridos": list(it.get("h2_sugeridos", [])) if isinstance(it.get("h2_sugeridos"), list) else [],
                "tips_seo": list(it.get("tips_seo", [])) if isinstance(it.get("tips_seo"), list) else [],
                "articulo": ""  # siempre vacío acá
            })
        return fixed[:3] if fixed else _fallback_ideas(keyword, pais, n=3)
    except Exception as e:
        print("❌ Error en generar_ideas_para_keyword:", e)
        return _fallback_ideas(keyword, pais, n=3)

def generar_articulo_para_keyword(
    keyword: str,
    h2_sugeridos: Optional[List[str]] = None,
    tono: str = "informativo"
) -> Dict[str, str]:
    """
    Devuelve {"html": "<article>...</article>"} con contenido SEO completo.
    """
    if not keyword:
        return {"html": _fallback_article("contenido")}

    if client is None:
        return {"html": _fallback_article(keyword)}

    extra_h2 = ""
    if h2_sugeridos:
        joined = "; ".join([h for h in h2_sugeridos if isinstance(h, str) and h.strip()])
        if joined:
            extra_h2 = f"\nRespetá estos H2 (si aplica): {joined}\n"

    prompt = f"""
Escribí un ARTÍCULO SEO completo en español, con tono {tono}, optimizado para la keyword "{keyword}".
Requisitos:
- Estructura HTML semántica dentro de <article>...</article>.
- Un solo <h1> inicial con el título del artículo.
- 3 a 6 <h2> con secciones claras y párrafos explicativos (no frases sueltas).
- Incluí una sección final "Tips SEO" como texto corrido (sin listas).
- Evitá negritas/strong; preferí texto plano y párrafos de 3-5 líneas.
- Nada de texto fuera del <article>.
{extra_h2}
Devolvé SOLO el HTML.
""".strip()

    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Sos un redactor SEO profesional especializado en español neutro."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
        )
        contenido = (resp.choices[0].message.content or "").strip()

        if "<article" not in contenido.lower():
            contenido = _md_to_html_minimal(contenido)
        else:
            contenido = _ensure_article_wrapper(contenido)

        return {"html": contenido}
    except Exception as e:
        print("❌ Error en generar_articulo_para_keyword:", e)
        return {"html": _fallback_article(keyword)}

# =========================================================
# Optimización de artículos existentes
# =========================================================
def optimizar_articulo_html(html: str, keyword: str, target_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Optimiza el HTML de un artículo para SEO y legibilidad.
    Devuelve: {"ok": True/False, "html": "<article>...</article>", "files": {...}}
    - Usa OpenAI si hay API; si no, hace un 'fallback' local.
    - Mantiene estructura <article> y evita <strong>/<b> innecesario.
    """
    try:
        src = (html or "").strip()
        if not src:
            return {"ok": False, "error": "no_html"}

        # Si el modelo no está disponible, limpieza mínima + normalización
        if client is None:
            cleaned = re.sub(r"^```(?:html)?\s*|\s*```$", "", src, flags=re.I | re.M)
            if "<article" not in cleaned.lower():
                cleaned = _md_to_html_minimal(cleaned)
            else:
                cleaned = _ensure_article_wrapper(cleaned)
            cleaned = re.sub(r"<\s*(strong|b)\b[^>]*>(.*?)<\s*/\s*\1\s*>", r"\2", cleaned, flags=re.I | re.S)
            return {"ok": True, "html": cleaned, "files": {}}

        sitio = target_url or "el sitio del usuario"
        prompt = f"""
Sos editor SEO senior. Recibís un ARTÍCULO en HTML y debés devolverlo optimizado para la keyword "{keyword}",
apuntando a {sitio}. Reglas:
- Devolvé SOLO HTML dentro de <article>...</article>.
- Conservá la estructura semántica: 1 <h1> y 3–6 <h2> con párrafos útiles (no bullets sueltos).
- Remové <strong>/<b> innecesario; usá texto claro.
- Mejorá titulares, enlaces internos (texto ancla descriptivo) y claridad en párrafos.
- Sumá una sección final "Tips SEO" como texto corrido (no lista).
- NO agregues nada fuera del <article>.

HTML de entrada:
{src}
""".strip()

        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Sos un editor SEO profesional en español neutro."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
        )
        out = (resp.choices[0].message.content or "").strip()

        out = re.sub(r"^```(?:html)?\s*|\s*```$", "", out, flags=re.I | re.M).strip()
        if "<article" not in out.lower():
            out = _md_to_html_minimal(out)
        else:
            out = _ensure_article_wrapper(out)

        out = re.sub(r"<\s*(strong|b)\b[^>]*>(.*?)<\s*/\s*\1\s*>", r"\2", out, flags=re.I | re.S)

        return {"ok": True, "html": out, "files": {}}

    except Exception as e:
        print("❌ Error en optimizar_articulo_html:", e)
        return {"ok": False, "error": "server_error"}

# =========================================================
# Aliases de compatibilidad (no quitar)
# =========================================================
def generar_ideas_desde_keyword(keyword: str, pais: Optional[str] = None, n: int = 3) -> List[Dict[str, Any]]:
    """Alias compatible si en algún punto el backend llamó a otra función."""
    ideas = generar_ideas_para_keyword(keyword, pais)
    return ideas[:n] if isinstance(n, int) and n > 0 else ideas

def generar_articulo_html(
    keyword: str,
    pais: Optional[str] = None,
    h2_sugeridos: Optional[List[str]] = None,
    tono: str = "informativo"
) -> Dict[str, str]:
    """Alias que ignora 'pais' pero mantiene firma."""
    return generar_articulo_para_keyword(keyword, h2_sugeridos=h2_sugeridos, tono=tono)

def optimizar_articulo(html: str, keyword: str, target_url: Optional[str] = None) -> Dict[str, Any]:
    """Alias simple para mantener nombres previos en el backend."""
    return optimizar_articulo_html(html=html, keyword=keyword, target_url=target_url)

def optimizar_contenido_html(html: str, keyword: str, target_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Alias de compatibilidad: algunos endpoints llaman a optimizar_contenido_html.
    Redirige a optimizar_articulo_html para no romper integraciones.
    """
    return optimizar_articulo_html(html=html, keyword=keyword, target_url=target_url)