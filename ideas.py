# -*- coding: utf-8 -*-
import os
import json
import re
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# ============= Carga de .env y cliente OpenAI opcional ============
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()  # podés cambiarlo por gpt-4o o gpt-4
client = None
if OPENAI_API_KEY:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as _e:
        client = None

# ======================= Helpers internos =========================
_CODE_FENCE_RE = re.compile(r"^```[\w-]*\s*([\s\S]*?)\s*```$", re.I | re.M)

def _strip_code_fences(text: str) -> str:
    """
    Quita bloque de code fences tipo:
    ```html
    ...contenido...
    ```
    o cualquier variante ```xxx ... ``` (al inicio/fin).
    También maneja el caso de que empiece con ``` y solo tenga etiqueta.
    """
    if not text:
        return ""
    t = text.strip()
    m = _CODE_FENCE_RE.match(t)
    if m:
        return m.group(1).strip()
    # Si arranca con ``` pero sin bloque estándar, intentar sacar la 1a línea
    if t.startswith("```"):
        lines = t.splitlines()
        if lines:
            head = lines[0].strip("`").strip()  # ej: "html" o "json" o vacío
            if head == "" or head.isalpha():
                t = "\n".join(lines[1:]).strip()
    return t

def _clean_json_block(s: str) -> str:
    """
    Extrae el primer bloque que parece un array JSON desde la respuesta del modelo.
    Más robusto: primero quita code fences si existen.
    """
    if not s:
        return "[]"
    s = _strip_code_fences(s)
    # Buscar desde el primer '[' hasta el último ']'
    start = s.find("[")
    end = s.rfind("]")
    if start != -1 and end != -1 and end > start:
        return s[start:end+1].strip()
    return "[]"

def _md_to_html_minimal(md: str) -> str:
    """
    Conversión mínima de Markdown a HTML para casos en los que el modelo no
    devuelve HTML puro. No pretende ser completa, solo lo esencial.
    """
    if not md:
        return ""
    text = md.strip()

    # Quitar fences de código (global)
    text = re.sub(r"```[\w-]*\s*([\s\S]*?)\s*```", lambda m: m.group(1), text, flags=re.S)

    # Encabezados # -> h1, ## -> h2, ### -> h3
    text = re.sub(r"(?m)^\s*#\s+(.*)$", r"<h1>\1</h1>", text)
    text = re.sub(r"(?m)^\s*##\s+(.*)$", r"<h2>\1</h2>", text)
    text = re.sub(r"(?m)^\s*###\s+(.*)$", r"<h3>\1</h3>", text)

    # Quitar **negritas** y *itálicas* simples
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)

    # Bullets simples -> párrafos
    text = re.sub(r"(?m)^\s*-\s+(.*)$", r"<p>\1</p>", text)

    # Separar líneas dobles en <p> si no hay ya etiquetas
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    wrapped = []
    for p in parts:
        if p.startswith("<h") or p.startswith("<p>") or p.startswith("<ul>") or p.startswith("<article>"):
            wrapped.append(p)
        else:
            wrapped.append(f"<p>{p}</p>")

    html = "\n".join(wrapped).strip()
    # Asegurar <article>
    if "<article" not in html.lower():
        html = f"<article>\n{html}\n</article>"
    return html

def _ensure_article_wrapper(html: str) -> str:
    if not html:
        return "<article></article>"
    if re.search(r"<article\b", html, flags=re.I):
        return html
    return f"<article>\n{html}\n</article>"

def _fallback_ideas(keyword: str, pais: Optional[str], n: int = 3) -> List[Dict[str, Any]]:
    """
    Genera ideas sin LLM, para modo offline/errores.
    """
    base = [
        {
            "keyword": f"{keyword} guía {pais or ''}".strip(),
            "titulo": f"Guía completa sobre {keyword} en {pais}" if pais else f"Guía completa sobre {keyword}",
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
            "titulo": f"Novedades y cambios sobre {keyword} en 2025" if pais else f"Novedades y cambios sobre {keyword} en 2025",
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
    Artículo HTML completo de fallback (no un placeholder corto).
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
"""
    return _ensure_article_wrapper(cuerpo.strip())

# ================== API principal expuesta =======================
def generar_ideas_para_keyword(keyword: str, pais: Optional[str]) -> List[Dict[str, Any]]:
    """
    Devuelve una lista de ideas:
    [
      {
        "keyword": str,
        "titulo": str,
        "palabras_clave": [str],
        "h2_sugeridos": [str],
        "tips_seo": [str],
        "articulo": ""   # siempre string vacío acá
      }, ...
    ]
    """
    if not keyword:
        return []

    # Si no hay cliente OpenAI, modo offline
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
"""

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

        # Validación mínima + normalización
        fixed = []
        for it in ideas if isinstance(ideas, list) else []:
            fixed.append({
                "keyword": str(it.get("keyword", keyword)),
                "titulo": str(it.get("titulo", keyword)).strip() or keyword,
                "palabras_clave": list(it.get("palabras_clave", [])) if isinstance(it.get("palabras_clave"), list) else [],
                "h2_sugeridos": list(it.get("h2_sugeridos", [])) if isinstance(it.get("h2_sugeridos"), list) else [],
                "tips_seo": list(it.get("tips_seo", [])) if isinstance(it.get("tips_seo"), list) else [],
                "articulo": ""  # siempre vacío acá
            })
            # --- asegurar keywords únicos dentro del batch ---
        _seen = set()
        for i, it in enumerate(fixed):
            k = (it.get("keyword") or "").strip().lower()
            if not k:
                k = f"{keyword.strip()} idea {i+1}"
                it["keyword"] = k
            if k in _seen:
                # usa parte del título para diferenciar
                t = (it.get("titulo") or "").strip()
                t_slug = re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:40] or f"idea-{i+1}"
                it["keyword"] = f"{it['keyword']} — {t_slug}"
            _seen.add((it.get("keyword") or "").strip().lower())
        return fixed[:3] if fixed else _fallback_ideas(keyword, pais, n=3)
    except Exception as e:
        print("❌ Error en generar_ideas_para_keyword:", e)
        return _fallback_ideas(keyword, pais, n=3)

def generar_articulo_para_keyword(keyword: str, h2_sugeridos: Optional[List[str]] = None, tono: str = "informativo") -> Dict[str, str]:
    """
    Devuelve {"html": "<article>...</article>"} con contenido SEO completo.
    """
    if not keyword:
        return {"html": _fallback_article("contenido")}

    if client is None:
        return {"html": _fallback_article(keyword)}

    # Construcción de prompt
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
"""

    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Sos un redactor SEO profesional especializado en español neutro."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
        )
        contenido = resp.choices[0].message.content.strip()
        # 👇 Quitar siempre code fences tipo ```html ... ```
        contenido = _strip_code_fences(contenido)

        # Si no parece HTML, aplicar conversión mínima desde Markdown
        if "<article" not in contenido.lower():
            contenido = _md_to_html_minimal(contenido)
        else:
            contenido = _ensure_article_wrapper(contenido)

        return {"html": contenido}
    except Exception as e:
        print("❌ Error en generar_articulo_para_keyword:", e)
        return {"html": _fallback_article(keyword)}

# ======================= Aliases de compat =======================
def generar_ideas_desde_keyword(keyword: str, pais: Optional[str] = None, n: int = 3) -> List[Dict[str, Any]]:
    """
    Alias compatible si en algún punto el backend llamó a otra función.
    """
    ideas = generar_ideas_para_keyword(keyword, pais)
    return ideas[:n] if isinstance(n, int) and n > 0 else ideas

def generar_articulo_html(keyword: str, pais: Optional[str] = None, h2_sugeridos: Optional[List[str]] = None, tono: str = "informativo") -> Dict[str, str]:
    """
    Alias que ignora 'pais' (no es necesario para el artículo) pero mantiene firma.
    """
    return generar_articulo_para_keyword(keyword, h2_sugeridos=h2_sugeridos, tono=tono)