"""Análisis de producciones con un modelo de visión (API de Anthropic).

Principios de diseño (ver informe):
- la clasificación la define el esquema de la docente, no el modelo;
- toda clasificación debe llevar una cita literal de lo escrito por el estudiante;
- si no hay evidencia suficiente, se marca y se pide revisión humana;
- los resultados son hipótesis que la docente verifica.
"""
import base64
import json
import os
import re

MODELO_POR_DEFECTO = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")

CERTEZAS = ("alta", "media", "baja")


def construir_system_prompt(esquema):
    estrategias = "\n".join(
        f"- {c}: {i['nombre']}. {i.get('descripcion', '')}" for c, i in esquema["estrategias"].items()
    )
    dificultades = "\n".join(
        f"- {c}: {i['nombre']}. {i.get('descripcion', '')}" for c, i in esquema["dificultades"].items()
    )
    return f"""Sos un asistente de una docente de matemática que analiza producciones escritas de estudiantes de primer año de secundaria sobre fracciones. Tu tarea es transcribir y clasificar con un esquema de codificación que define la docente. No evaluás ni calificás: describís y proponés hipótesis que la docente verificará.

Problema planteado a los estudiantes: {esquema['enunciado']}
Contexto de la figura: {esquema.get('contexto', '(no informado)')}
Respuesta esperada: {esquema.get('respuesta_esperada', '(no informada)')}

ESTRATEGIAS (códigos disponibles):
{estrategias}

DIFICULTADES (códigos disponibles):
{dificultades}

REGLAS:
1. Transcribí de manera literal lo que el estudiante escribió. Marcá con [ilegible] lo que no puedas leer; nunca lo completes ni lo corrijas. Respetá los errores de ortografía y de notación.
2. Usá solo códigos del esquema. Si ninguno corresponde, no inventes códigos: dejá la lista vacía y explicalo en 'observaciones'.
3. Cada estrategia y cada dificultad debe incluir una 'cita' textual breve de lo escrito (o una descripción de lo dibujado, entre corchetes) que la respalde. Sin cita, no la incluyas.
4. Indicá una 'certeza' (alta, media o baja) para cada clasificación. Si la evidencia es escasa o ambigua, usá 'baja'.
5. No atribuyas razonamientos que el estudiante no escribió ni dibujó. Una dificultad es una hipótesis, no un hecho.
6. Si la imagen está borrosa, cortada, rotada de modo que no se lee, o no contiene una producción, poné requiere_revision en true y explicá el motivo.
7. No transcribas nombres de personas: reemplazalos por [nombre].

Respondé únicamente con un objeto JSON, sin texto adicional ni bloques de código, con esta forma exacta:
{{
  "transcripcion": "texto literal",
  "respuesta_fraccion": "por ejemplo 1/4, o null si no responde con una fracción",
  "tiene_justificacion": true,
  "menciona_partes_iguales": false,
  "estrategias": [{{"codigo": "S1", "cita": "...", "certeza": "alta"}}],
  "dificultades": [{{"codigo": "D1", "cita": "...", "certeza": "media", "hipotesis": "..."}}],
  "observaciones": "",
  "requiere_revision": false,
  "motivo_revision": ""
}}"""


def extraer_json(texto):
    """Extrae el primer objeto JSON de un texto, tolerando bloques de código."""
    if not texto:
        raise ValueError("Respuesta vacía.")
    limpio = re.sub(r"^```(?:json)?|```$", "", texto.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(limpio)
    except json.JSONDecodeError:
        inicio, fin = limpio.find("{"), limpio.rfind("}")
        if inicio == -1 or fin == -1 or fin <= inicio:
            raise ValueError("No se encontró un objeto JSON en la respuesta.")
        return json.loads(limpio[inicio : fin + 1])


def _normalizar_lista(items, codigos_validos, desconocidos):
    salida = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        codigo = str(item.get("codigo", "")).strip().upper()
        if codigo not in codigos_validos:
            desconocidos.append(codigo or "(vacío)")
            continue
        certeza = str(item.get("certeza", "baja")).strip().lower()
        if certeza not in CERTEZAS:
            certeza = "baja"
        entrada = {"codigo": codigo, "cita": str(item.get("cita", "")).strip(), "certeza": certeza}
        if "hipotesis" in item:
            entrada["hipotesis"] = str(item.get("hipotesis", "")).strip()
        if not entrada["cita"]:
            # Sin cita no hay evidencia: se conserva pero con certeza baja y revisión.
            entrada["certeza"] = "baja"
            entrada["sin_cita"] = True
        salida.append(entrada)
    return salida


def normalizar_resultado(crudo, esquema):
    """Valida el JSON del modelo contra el esquema y marca lo que requiere revisión."""
    desconocidos = []
    estrategias = _normalizar_lista(crudo.get("estrategias"), set(esquema["estrategias"]), desconocidos)
    dificultades = _normalizar_lista(crudo.get("dificultades"), set(esquema["dificultades"]), desconocidos)
    respuesta = crudo.get("respuesta_fraccion")
    respuesta = None if respuesta in (None, "", "null") else str(respuesta).strip().replace(" ", "")
    motivos = []
    if crudo.get("requiere_revision"):
        motivos.append(str(crudo.get("motivo_revision", "")).strip() or "Señalado por el modelo.")
    if desconocidos:
        motivos.append("Códigos fuera del esquema: " + ", ".join(sorted(set(desconocidos))))
    if any(e.get("sin_cita") for e in estrategias + dificultades):
        motivos.append("Hay clasificaciones sin cita que las respalde.")
    if any(e["certeza"] == "baja" for e in estrategias + dificultades):
        motivos.append("Hay clasificaciones con certeza baja.")
    return {
        "transcripcion": str(crudo.get("transcripcion", "")).strip(),
        "respuesta_fraccion": respuesta,
        "tiene_justificacion": bool(crudo.get("tiene_justificacion", False)),
        "menciona_partes_iguales": bool(crudo.get("menciona_partes_iguales", False)),
        "estrategias": estrategias,
        "dificultades": dificultades,
        "observaciones": str(crudo.get("observaciones", "")).strip(),
        "requiere_revision": bool(motivos),
        "motivo_revision": " | ".join(motivos),
    }


def crear_cliente(api_key):
    import anthropic  # importación diferida: la app funciona en modo demo sin la librería

    return anthropic.Anthropic(api_key=api_key)


def _texto_de_respuesta(respuesta):
    return "".join(b.text for b in respuesta.content if getattr(b, "type", "") == "text")


def analizar_imagen(cliente, modelo, imagen_jpeg, esquema):
    """Analiza una imagen preparada y devuelve el resultado normalizado."""
    datos = base64.standard_b64encode(imagen_jpeg).decode("utf-8")
    respuesta = cliente.messages.create(
        model=modelo,
        max_tokens=1500,
        temperature=0,
        system=construir_system_prompt(esquema),
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": datos}},
                    {"type": "text", "text": "Analizá esta producción siguiendo las reglas y respondé solo con el JSON."},
                ],
            }
        ],
    )
    return normalizar_resultado(extraer_json(_texto_de_respuesta(respuesta)), esquema)


PROMPT_INTERVENCIONES = """Sos un asistente de una docente de matemática. A partir de un resumen cuantitativo de producciones de estudiantes y de un esquema de codificación, proponés intervenciones para la puesta en común. Seguí estos criterios (Rodríguez et al., 2017; Stein et al., 2008):
- No digas si una resolución está bien o mal: formulá preguntas abiertas.
- No des más información que la que contiene la pregunta; no conduzcas la respuesta.
- Pedí explicaciones aun cuando la respuesta sea correcta.
- Para la puesta en común, seleccioná y secuenciá producciones (por su identificador) yendo de lo más frecuente o más productivo de discutir a lo que consolida la validación por argumentos.
Respondé en español rioplatense, en Markdown breve, con tres secciones: (1) Dificultades prioritarias y por qué, (2) Preguntas abiertas por dificultad, (3) Orden sugerido de producciones para la puesta en común, con una línea de justificación por producción. Recordá al final que son propuestas para que la docente decida."""


def generar_intervenciones(cliente, modelo, resumen, esquema):
    contenido = (
        "ESQUEMA:\n" + json.dumps(esquema, ensure_ascii=False)
        + "\n\nRESUMEN DE PRODUCCIONES:\n" + json.dumps(resumen, ensure_ascii=False)
    )
    respuesta = cliente.messages.create(
        model=modelo,
        max_tokens=1800,
        temperature=0.3,
        system=PROMPT_INTERVENCIONES,
        messages=[{"role": "user", "content": contenido}],
    )
    return _texto_de_respuesta(respuesta)


# --- Modo demostración (no envía nada a ningún servicio) -------------------

_DEMO = [
    {
        "transcripcion": "Es 4/1 porque está dividida en 4 porciones y uno está pintada.",
        "respuesta_fraccion": "4/1",
        "tiene_justificacion": True,
        "menciona_partes_iguales": False,
        "estrategias": [{"codigo": "S1", "cita": "está dividida en 4 porciones y uno está pintada", "certeza": "alta"}],
        "dificultades": [
            {"codigo": "D2", "cita": "4/1", "certeza": "media", "hipotesis": "Total como numerador, partes tomadas como denominador."},
            {"codigo": "D1", "cita": "dividida en 4 porciones", "certeza": "media", "hipotesis": "No verifica que las partes sean iguales."},
        ],
        "observaciones": "", "requiere_revision": False, "motivo_revision": "",
    },
    {
        "transcripcion": "La fracción es 1/4 porque hay cuatro partes y una está pintada, en este caso pero se puede pintar más.",
        "respuesta_fraccion": "1/4",
        "tiene_justificacion": True,
        "menciona_partes_iguales": False,
        "estrategias": [{"codigo": "S1", "cita": "hay cuatro partes y una está pintada", "certeza": "alta"}],
        "dificultades": [
            {"codigo": "D1", "cita": "hay cuatro partes", "certeza": "media", "hipotesis": "No menciona partes iguales."},
            {"codigo": "D4", "cita": "se puede pintar más", "certeza": "media", "hipotesis": "Piensa la fracción como atributo de lo pintado."},
        ],
        "observaciones": "", "requiere_revision": False, "motivo_revision": "",
    },
    {
        "transcripcion": "Si trazo la diagonal completa quedan 4 veces el mismo triángulo. Es 1/4.",
        "respuesta_fraccion": "1/4",
        "tiene_justificacion": True,
        "menciona_partes_iguales": True,
        "estrategias": [{"codigo": "S2", "cita": "quedan 4 veces el mismo triángulo", "certeza": "alta"}],
        "dificultades": [],
        "observaciones": "Verifica la igualdad de las partes.", "requiere_revision": False, "motivo_revision": "",
    },
    {
        "transcripcion": "Representa un triángulo rectángulo.",
        "respuesta_fraccion": None,
        "tiene_justificacion": False,
        "menciona_partes_iguales": False,
        "estrategias": [{"codigo": "S6", "cita": "un triángulo rectángulo", "certeza": "alta"}],
        "dificultades": [{"codigo": "D3", "cita": "un triángulo rectángulo", "certeza": "alta", "hipotesis": "No interpreta que se pide una fracción."}],
        "observaciones": "", "requiere_revision": False, "motivo_revision": "",
    },
]


def analizar_demo(indice, esquema):
    """Resultado de ejemplo: NO lee la imagen. Sirve para recorrer la aplicación sin enviar datos."""
    resultado = normalizar_resultado(_DEMO[indice % len(_DEMO)], esquema)
    resultado["es_demo"] = True
    resultado["transcripcion"] = "[EJEMPLO DE DEMOSTRACIÓN: no corresponde a esta imagen] " + resultado["transcripcion"]
    return resultado


def intervenciones_demo(resumen, esquema):
    lineas = ["**Modo demostración.** Con la API se generaría aquí una propuesta personalizada. Mientras tanto, estas son las preguntas del esquema:\n"]
    for codigo, n in resumen.get("dificultades_frecuencia", {}).items():
        info = esquema["dificultades"].get(codigo)
        if info:
            lineas.append(f"**{codigo} · {info['nombre']}** ({n} producciones)")
            lineas.extend(f"- {p}" for p in info.get("preguntas", []))
            lineas.append("")
    return "\n".join(lineas)
