"""Agregación, comparación entre lotes y concordancia docente–IA."""
from collections import Counter

import pandas as pd

SIN_FRACCION = "(sin fracción)"


def valores_finales(item):
    """Valores vigentes: los de la docente si verificó; si no, los de la IA."""
    docente = item.get("docente")
    ia = item.get("ia")
    if docente and docente.get("verificado"):
        return {
            "respuesta_fraccion": docente.get("respuesta_fraccion") or None,
            "tiene_justificacion": bool(docente.get("tiene_justificacion")),
            "menciona_partes_iguales": bool(docente.get("menciona_partes_iguales")),
            "estrategias": list(docente.get("estrategias", [])),
            "dificultades": list(docente.get("dificultades", [])),
            "verificado": True,
            "requiere_revision": False,
        }
    if ia:
        return {
            "respuesta_fraccion": ia["respuesta_fraccion"],
            "tiene_justificacion": ia["tiene_justificacion"],
            "menciona_partes_iguales": ia["menciona_partes_iguales"],
            "estrategias": [e["codigo"] for e in ia["estrategias"]],
            "dificultades": [d["codigo"] for d in ia["dificultades"]],
            "verificado": False,
            "requiere_revision": ia["requiere_revision"],
        }
    return None


def construir_dataframe(items):
    filas = []
    for item in items:
        v = valores_finales(item)
        if v is None:
            continue
        filas.append({"id": item["id"], "lote": item["lote"], **v})
    columnas = ["id", "lote", "respuesta_fraccion", "tiene_justificacion", "menciona_partes_iguales",
                "estrategias", "dificultades", "verificado", "requiere_revision"]
    return pd.DataFrame(filas, columns=columnas)


def tabla_respuestas(df):
    if df.empty:
        return pd.DataFrame()
    r = df.assign(respuesta=df["respuesta_fraccion"].fillna(SIN_FRACCION))
    return r.pivot_table(index="respuesta", columns="lote", values="id", aggfunc="count", fill_value=0)


def tabla_codigos(df, columna):
    """Frecuencia de códigos (estrategias o dificultades) por lote."""
    if df.empty:
        return pd.DataFrame()
    filas = [(codigo, fila["lote"]) for _, fila in df.iterrows() for codigo in fila[columna]]
    if not filas:
        return pd.DataFrame()
    tabla = pd.DataFrame(filas, columns=["codigo", "lote"])
    return tabla.pivot_table(index="codigo", columns="lote", aggfunc="size", fill_value=0)


def porcentajes_por_lote(df):
    if df.empty:
        return pd.DataFrame()
    g = df.groupby("lote")
    return pd.DataFrame({
        "n": g["id"].count(),
        "% con justificación": (g["tiene_justificacion"].mean() * 100).round(0),
        "% menciona partes iguales": (g["menciona_partes_iguales"].mean() * 100).round(0),
        "% verificadas por la docente": (g["verificado"].mean() * 100).round(0),
    })


# --- Concordancia ----------------------------------------------------------

def cohen_kappa(a, b):
    """Kappa de Cohen entre dos listas de etiquetas. Devuelve None si no es calculable."""
    if len(a) != len(b) or not a:
        return None
    n = len(a)
    observado = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    esperado = sum((ca[k] / n) * (cb[k] / n) for k in set(ca) | set(cb))
    if esperado == 1:
        return 1.0 if observado == 1 else None
    return (observado - esperado) / (1 - esperado)


def jaccard(a, b):
    a, b = set(a), set(b)
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def comparar_ia_docente(items):
    """Compara lo que dijo la IA con lo verificado por la docente (solo ítems verificados)."""
    pares = [(i["ia"], i["docente"]) for i in items if i.get("ia") and i.get("docente") and i["docente"].get("verificado")]
    if not pares:
        return None
    etiqueta = lambda x: x or SIN_FRACCION
    resultado = {
        "n_verificadas": len(pares),
        "kappa_respuesta": cohen_kappa([etiqueta(p[0]["respuesta_fraccion"]) for p in pares],
                                       [etiqueta(p[1].get("respuesta_fraccion")) for p in pares]),
        "kappa_justificacion": cohen_kappa([p[0]["tiene_justificacion"] for p in pares],
                                           [bool(p[1].get("tiene_justificacion")) for p in pares]),
        "kappa_partes_iguales": cohen_kappa([p[0]["menciona_partes_iguales"] for p in pares],
                                            [bool(p[1].get("menciona_partes_iguales")) for p in pares]),
        "acuerdo_estrategias": sum(jaccard([e["codigo"] for e in p[0]["estrategias"]], p[1].get("estrategias", [])) for p in pares) / len(pares),
        "acuerdo_dificultades": sum(jaccard([d["codigo"] for d in p[0]["dificultades"]], p[1].get("dificultades", [])) for p in pares) / len(pares),
    }
    return resultado


# --- Resúmenes -------------------------------------------------------------

def resumen_para_ia(items):
    """Resumen sin imágenes ni transcripciones, apto para enviar a generar intervenciones."""
    df = construir_dataframe(items)
    if df.empty:
        return {"n": 0}
    est, dif = Counter(), Counter()
    ejemplos = {}
    for _, f in df.iterrows():
        est.update(f["estrategias"])
        dif.update(f["dificultades"])
        for c in f["dificultades"]:
            ejemplos.setdefault(c, []).append(f["id"])
    return {
        "n": int(len(df)),
        "respuestas_frecuencia": df["respuesta_fraccion"].fillna(SIN_FRACCION).value_counts().to_dict(),
        "porcentaje_con_justificacion": round(float(df["tiene_justificacion"].mean() * 100)),
        "porcentaje_menciona_partes_iguales": round(float(df["menciona_partes_iguales"].mean() * 100)),
        "estrategias_frecuencia": dict(est.most_common()),
        "dificultades_frecuencia": dict(dif.most_common()),
        "ids_por_dificultad": ejemplos,
        "ids_por_respuesta": {r: g["id"].tolist() for r, g in df.assign(r=df["respuesta_fraccion"].fillna(SIN_FRACCION)).groupby("r")},
    }


def informe_markdown(items, esquema, intervenciones=None):
    df = construir_dataframe(items)
    lineas = ["# Informe de análisis de producciones", "", f"Problema: {esquema['enunciado']}", ""]
    if df.empty:
        return "\n".join(lineas + ["No hay producciones analizadas."])
    lineas += [f"Producciones analizadas: {len(df)} (verificadas por la docente: {int(df['verificado'].sum())}).", ""]
    lineas += ["## Respuestas por lote", "", tabla_respuestas(df).to_markdown(), ""]
    for titulo, col, clave in (("Estrategias", "estrategias", "estrategias"), ("Dificultades", "dificultades", "dificultades")):
        t = tabla_codigos(df, col)
        if not t.empty:
            t.index = [f"{c} · {esquema[clave].get(c, {}).get('nombre', c)}" for c in t.index]
            lineas += [f"## {titulo} por lote", "", t.to_markdown(), ""]
    lineas += ["## Porcentajes por lote", "", porcentajes_por_lote(df).to_markdown(), ""]
    comp = comparar_ia_docente(items)
    if comp:
        lineas += ["## Concordancia entre la IA y la docente", ""]
        for k, v in comp.items():
            lineas.append(f"- {k}: {'no calculable' if v is None else (round(v, 2) if isinstance(v, float) else v)}")
        lineas.append("")
    if intervenciones:
        lineas += ["## Intervenciones propuestas", "", intervenciones, ""]
    lineas += ["---", "Las clasificaciones de la IA son hipótesis; solo las producciones marcadas como verificadas reflejan el criterio docente."]
    return "\n".join(lineas)
