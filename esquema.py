"""Esquema de codificación didáctico por defecto.

Surge del análisis de las planificaciones de Práctica Docente 3 y de una primera
lectura de producciones de primer año sobre fracciones. La docente puede editarlo
desde la aplicación: lo importante es que el esquema lo defina ella.
"""
from copy import deepcopy

ESQUEMA_POR_DEFECTO = {
    "enunciado": "¿Qué fracción representa la parte pintada?",
    "contexto": (
        "Figura rectangular formada por regiones de formas distintas pero de igual "
        "área. La parte pintada es un triángulo que representa 1/4 del entero."
    ),
    "respuesta_esperada": "1/4",
    "estrategias": {
        "S1": {
            "nombre": "Conteo de partes sin verificar que sean iguales",
            "descripcion": "Cuenta las regiones y las pintadas (por ejemplo, 'está dividida en 4 y 1 está pintada') sin comprobar que las partes sean iguales.",
        },
        "S2": {
            "nombre": "Subdivisión con trazado y verificación",
            "descripcion": "Traza líneas para subdividir la figura y comprueba que las partes son iguales (por ejemplo, el triángulo cabe 4 veces en el entero).",
        },
        "S3": {
            "nombre": "Recurso a un contexto cotidiano",
            "descripcion": "Apela a una situación como una torta, pizzas o juguetes para justificar la fracción.",
        },
        "S4": {
            "nombre": "Conteo por tipo de figura",
            "descripcion": "Cuenta triángulos y cuadriláteros por separado (por ejemplo, 'hay dos triángulos y uno está pintado').",
        },
        "S5": {
            "nombre": "Subdivisión en más partes con conteo erróneo",
            "descripcion": "Subdivide la figura en más partes (por ejemplo, 8) y cuenta mal las partes pintadas.",
        },
        "S6": {
            "nombre": "Denominación de la figura",
            "descripcion": "Responde con el nombre de la figura (triángulo, rectángulo) en lugar de una fracción.",
        },
        "S7": {
            "nombre": "Respuesta sin justificación",
            "descripcion": "Da una respuesta pero no escribe ninguna justificación.",
        },
    },
    "dificultades": {
        "D1": {
            "nombre": "Las partes iguales no se explicitan",
            "descripcion": "La justificación no menciona que las partes deben ser iguales o del mismo tamaño.",
            "preguntas": [
                "¿Cómo podrías comprobar que las cuatro partes son iguales?",
                "Si las partes fueran desiguales, ¿la parte pintada seguiría representando 1/4? (presentar una figura con cuatro partes desiguales)",
            ],
        },
        "D2": {
            "nombre": "Error de sentido en el orden (4/1)",
            "descripcion": "Escribe el total como numerador y las partes tomadas como denominador, con una concepción de 'total de elementos y elementos tomados'.",
            "preguntas": [
                "¿Qué representa el 4 y qué representa el 1 en tu fracción?",
                "¿4/1 es más o menos que el entero? ¿Cuántos enteros son 4/1?",
            ],
        },
        "D3": {
            "nombre": "No reconoce qué se pide",
            "descripcion": "Responde con el nombre de la figura u otra cosa distinta de una fracción.",
            "preguntas": [
                "Escribí con un número cuánto del entero es la parte pintada.",
                "¿Qué te dice la palabra 'fracción' en la pregunta?",
            ],
        },
        "D4": {
            "nombre": "Idea de fracción variable (depende de lo pintado)",
            "descripcion": "Expresiones como 'en este caso, pero se puede pintar más' sugieren pensar la fracción como atributo de lo pintado y no como relación entre la parte y el entero.",
            "preguntas": [
                "Si pintás otra parte, ¿cambia la fracción? ¿Y si cambio el entero?",
                "¿Qué es lo que no cambia cuando pintás más?",
            ],
        },
        "D5": {
            "nombre": "Del conteo discreto a la medida continua",
            "descripcion": "Cuenta objetos o cuadrados y recurre a analogías con elementos separados (pizzas, juguetes) en lugar de considerar una parte del entero.",
            "preguntas": [
                "En tu ejemplo de las pizzas, ¿cuál sería el entero? ¿Y en esta figura?",
                "¿Se pueden comparar esas 4 partes si no son del mismo tamaño?",
            ],
        },
    },
}


def esquema_por_defecto():
    return deepcopy(ESQUEMA_POR_DEFECTO)


def validar_esquema(esquema):
    """Devuelve una lista de problemas (vacía si el esquema es válido)."""
    problemas = []
    for clave in ("enunciado", "estrategias", "dificultades"):
        if clave not in esquema:
            problemas.append(f"Falta la clave '{clave}'.")
    for bloque in ("estrategias", "dificultades"):
        datos = esquema.get(bloque, {})
        if not isinstance(datos, dict) or not datos:
            problemas.append(f"'{bloque}' debe ser un diccionario con al menos un código.")
            continue
        for codigo, info in datos.items():
            if not isinstance(info, dict) or "nombre" not in info:
                problemas.append(f"El código {codigo} de '{bloque}' necesita al menos un 'nombre'.")
    return problemas
