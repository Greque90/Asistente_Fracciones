"""Asistente docente para el análisis didáctico de producciones sobre fracciones.

Ejecutar con:  streamlit run app.py
"""
import json
import os

import streamlit as st

import analisis
import estadisticas as est
from esquema import esquema_por_defecto, validar_esquema
from imagenes import preparar_imagen

st.set_page_config(page_title="Asistente de análisis didáctico", page_icon="📐", layout="wide")


# ---------------------------------------------------------------- estado ---
def iniciar_estado():
    ss = st.session_state
    ss.setdefault("esquema", esquema_por_defecto())
    ss.setdefault("items", [])
    ss.setdefault("clave_uploader", 0)
    ss.setdefault("intervenciones", "")


iniciar_estado()
ss = st.session_state

# --------------------------------------------------------------- sidebar ---
with st.sidebar:
    st.title("📐 Asistente docente")
    st.caption("La IA propone; la docente decide. Todo se guarda solo en esta sesión.")
    modo = st.radio("Modo", ["Demostración (no envía nada)", "Con API de Anthropic"], index=0)
    demo = modo.startswith("Demostración")
    api_key, modelo = "", analisis.MODELO_POR_DEFECTO
    if not demo:
        api_key = st.text_input("Clave de la API", type="password", value=os.environ.get("ANTHROPIC_API_KEY", ""))
        modelo = st.text_input("Modelo", value=analisis.MODELO_POR_DEFECTO)
        st.warning("En este modo las imágenes se envían al servicio de la API para ser analizadas.")
    consentimiento = st.checkbox(
        "Confirmo que taché o recorté los nombres de los estudiantes y que la institución autorizó este uso.",
        value=demo,
        disabled=demo,
    )
    st.divider()
    st.metric("Producciones cargadas", len(ss["items"]))
    st.metric("Analizadas", sum(1 for i in ss["items"] if i.get("ia")))
    st.metric("Verificadas por la docente", sum(1 for i in ss["items"] if (i.get("docente") or {}).get("verificado")))


def cliente_api():
    if not api_key:
        st.error("Falta la clave de la API.")
        return None
    return analisis.crear_cliente(api_key)


# ------------------------------------------------------------------ tabs ---
t_esq, t_prep, t_an, t_ver, t_res, t_int, t_exp = st.tabs(
    ["1. Esquema", "2. Preparar", "3. Analizar", "4. Verificar", "5. Resultados", "6. Intervenciones", "7. Exportar"]
)

# ---- 1. Esquema -----------------------------------------------------------
with t_esq:
    st.subheader("Esquema de codificación")
    st.write(
        "El esquema lo define la docente a partir de las anticipaciones de la planificación. "
        "Se puede editar: cambiar el enunciado, las estrategias (S) y las dificultades (D)."
    )
    texto = st.text_area("Esquema (JSON)", value=json.dumps(ss["esquema"], ensure_ascii=False, indent=2), height=420)
    c1, c2 = st.columns(2)
    if c1.button("Aplicar esquema"):
        try:
            nuevo = json.loads(texto)
            problemas = validar_esquema(nuevo)
            if problemas:
                st.error("\n".join(problemas))
            else:
                ss["esquema"] = nuevo
                st.success("Esquema aplicado.")
        except json.JSONDecodeError as e:
            st.error(f"JSON inválido: {e}")
    if c2.button("Restaurar esquema por defecto"):
        ss["esquema"] = esquema_por_defecto()
        st.rerun()

# ---- 2. Preparar ----------------------------------------------------------
with t_prep:
    st.subheader("Cargar y preparar las producciones")
    st.info("Antes de analizar: corregí la orientación y recortá o tapá cualquier nombre. Los archivos no se guardan en disco.")
    lote = st.text_input("Nombre del lote", value="Lote 1", help="Por ejemplo, la fecha o la clase. Permite comparar lotes.")
    archivos = st.file_uploader(
        "Fotografías de las producciones", type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True, key=f"uploader_{ss['clave_uploader']}",
    )
    preparadas = []
    for n, archivo in enumerate(archivos, start=1):
        with st.expander(f"Fotografía {n}", expanded=len(archivos) <= 3):
            c = st.columns([1, 1, 2])
            rot = c[0].selectbox("Rotación (antihoraria)", [0, 90, 180, 270], key=f"rot_{archivo.file_id}_{ss['clave_uploader']}")
            rec = {
                "arriba": c[1].slider("Quitar arriba (%)", 0, 60, 0, key=f"ra_{archivo.file_id}_{ss['clave_uploader']}"),
                "abajo": c[1].slider("Quitar abajo (%)", 0, 60, 0, key=f"rb_{archivo.file_id}_{ss['clave_uploader']}"),
                "izquierda": c[1].slider("Quitar izquierda (%)", 0, 60, 0, key=f"ri_{archivo.file_id}_{ss['clave_uploader']}"),
                "derecha": c[1].slider("Quitar derecha (%)", 0, 60, 0, key=f"rd_{archivo.file_id}_{ss['clave_uploader']}"),
            }
            try:
                imagen, jpeg = preparar_imagen(archivo.getvalue(), rot, rec)
                c[2].image(imagen, caption="Así se enviará", use_container_width=True)
                preparadas.append(jpeg)
            except Exception as e:  # imagen dañada o formato no soportado
                c[2].error(f"No se pudo leer la imagen: {e}")
    if st.button("Agregar al conjunto", disabled=not preparadas):
        existentes = sum(1 for i in ss["items"] if i["lote"] == lote)
        for k, jpeg in enumerate(preparadas, start=existentes + 1):
            ss["items"].append({"id": f"{lote.replace(' ', '')}-P{k:02d}", "lote": lote, "imagen": jpeg,
                                "ia": None, "error": None, "docente": None})
        ss["clave_uploader"] += 1
        st.rerun()

# ---- 3. Analizar ----------------------------------------------------------
with t_an:
    st.subheader("Análisis con la IA")
    pendientes = [i for i in ss["items"] if i["ia"] is None]
    st.write(f"Pendientes de análisis: **{len(pendientes)}**")
    if not demo and not consentimiento:
        st.warning("Para usar la API confirmá en la barra lateral la anonimización y la autorización.")
    if st.button("Analizar pendientes", disabled=not pendientes or (not demo and not consentimiento)):
        cliente = None if demo else cliente_api()
        if demo or cliente:
            barra = st.progress(0.0)
            for n, item in enumerate(pendientes, start=1):
                try:
                    if demo:
                        item["ia"] = analisis.analizar_demo(n - 1, ss["esquema"])
                    else:
                        item["ia"] = analisis.analizar_imagen(cliente, modelo, item["imagen"], ss["esquema"])
                    item["error"] = None
                except Exception as e:
                    item["error"] = str(e)
                barra.progress(n / len(pendientes))
            st.success("Análisis terminado. Pasá a 'Verificar'.")
    for item in ss["items"]:
        if item.get("error"):
            st.error(f"{item['id']}: {item['error']}")

# ---- 4. Verificar ---------------------------------------------------------
with t_ver:
    st.subheader("Verificación de la docente")
    analizados = [i for i in ss["items"] if i["ia"]]
    if not analizados:
        st.info("Todavía no hay producciones analizadas.")
    else:
        solo_rev = st.checkbox("Mostrar primero las que requieren revisión", value=True)
        orden = sorted(analizados, key=lambda i: (not i["ia"]["requiere_revision"], i["id"])) if solo_rev else analizados
        etiquetas = {i["id"]: f"{i['id']} {'⚠️' if i['ia']['requiere_revision'] else ''} {'✅' if (i['docente'] or {}).get('verificado') else ''}" for i in orden}
        elegido = st.selectbox("Producción", list(etiquetas), format_func=lambda k: etiquetas[k])
        item = next(i for i in analizados if i["id"] == elegido)
        ia = item["ia"]
        col_img, col_ia = st.columns(2)
        col_img.image(item["imagen"], use_container_width=True)
        col_ia.markdown("**Transcripción (IA)**")
        col_ia.code(ia["transcripcion"] or "(vacía)", language=None)
        if ia["requiere_revision"]:
            col_ia.warning(ia["motivo_revision"])
        for etiqueta, clave in (("Estrategias", "estrategias"), ("Dificultades", "dificultades")):
            col_ia.markdown(f"**{etiqueta} propuestas**")
            for e in ia[clave]:
                nombre = ss["esquema"][clave].get(e["codigo"], {}).get("nombre", "")
                col_ia.markdown(f"- `{e['codigo']}` {nombre} · certeza {e['certeza']}  \n  cita: _{e['cita'] or 'sin cita'}_")
        base = item["docente"] or {
            "respuesta_fraccion": ia["respuesta_fraccion"], "tiene_justificacion": ia["tiene_justificacion"],
            "menciona_partes_iguales": ia["menciona_partes_iguales"],
            "estrategias": [e["codigo"] for e in ia["estrategias"]],
            "dificultades": [d["codigo"] for d in ia["dificultades"]], "comentario": "", "verificado": False,
        }
        with st.form(f"form_{item['id']}"):
            f1, f2, f3 = st.columns(3)
            resp = f1.text_input("Respuesta (fracción)", value=base.get("respuesta_fraccion") or "")
            just = f2.checkbox("Tiene justificación", value=base.get("tiene_justificacion", False))
            iguales = f3.checkbox("Menciona partes iguales", value=base.get("menciona_partes_iguales", False))
            estr = st.multiselect("Estrategias", list(ss["esquema"]["estrategias"]), default=[c for c in base["estrategias"] if c in ss["esquema"]["estrategias"]])
            dific = st.multiselect("Dificultades", list(ss["esquema"]["dificultades"]), default=[c for c in base["dificultades"] if c in ss["esquema"]["dificultades"]])
            coment = st.text_area("Comentario de la docente", value=base.get("comentario", ""))
            verif = st.checkbox("Marcar como verificada", value=base.get("verificado", False))
            if st.form_submit_button("Guardar"):
                item["docente"] = {"respuesta_fraccion": resp.strip().replace(" ", "") or None, "tiene_justificacion": just,
                                   "menciona_partes_iguales": iguales, "estrategias": estr, "dificultades": dific,
                                   "comentario": coment, "verificado": verif}
                st.success("Guardado.")

# ---- 5. Resultados --------------------------------------------------------
with t_res:
    st.subheader("Resultados por lote")
    df = est.construir_dataframe(ss["items"])
    if df.empty:
        st.info("Todavía no hay resultados.")
    else:
        st.caption("Se usan los valores de la docente cuando la producción está verificada; si no, los de la IA (hipótesis).")
        st.markdown("**Respuestas**")
        tabla = est.tabla_respuestas(df)
        st.dataframe(tabla)
        st.bar_chart(tabla)
        for titulo, col in (("Estrategias", "estrategias"), ("Dificultades", "dificultades")):
            t = est.tabla_codigos(df, col)
            if not t.empty:
                st.markdown(f"**{titulo}**")
                t.index = [f"{c} · {ss['esquema'][col].get(c, {}).get('nombre', c)}" for c in t.index]
                st.dataframe(t)
                st.bar_chart(t)
        st.markdown("**Porcentajes**")
        st.dataframe(est.porcentajes_por_lote(df))

# ---- 6. Intervenciones ----------------------------------------------------
with t_int:
    st.subheader("Orientación de las intervenciones")
    resumen = est.resumen_para_ia(ss["items"])
    if resumen.get("n", 0) == 0:
        st.info("Primero analizá producciones.")
    else:
        st.markdown("**Dificultades más frecuentes y preguntas abiertas del esquema**")
        for codigo, n in resumen["dificultades_frecuencia"].items():
            info = ss["esquema"]["dificultades"].get(codigo)
            if info:
                st.markdown(f"**{codigo} · {info['nombre']}** ({n} producciones: {', '.join(resumen['ids_por_dificultad'][codigo])})")
                for p in info.get("preguntas", []):
                    st.markdown(f"- {p}")
        st.divider()
        st.caption("La propuesta de secuenciación se genera solo con el resumen cuantitativo (sin imágenes ni transcripciones).")
        if st.button("Generar propuesta de puesta en común"):
            if demo:
                ss["intervenciones"] = analisis.intervenciones_demo(resumen, ss["esquema"])
            else:
                cliente = cliente_api()
                if cliente:
                    try:
                        ss["intervenciones"] = analisis.generar_intervenciones(cliente, modelo, resumen, ss["esquema"])
                    except Exception as e:
                        st.error(str(e))
        if ss["intervenciones"]:
            st.markdown(ss["intervenciones"])

# ---- 7. Exportar ----------------------------------------------------------
with t_exp:
    st.subheader("Exportar y comparar con la docente")
    df = est.construir_dataframe(ss["items"])
    comp = est.comparar_ia_docente(ss["items"])
    if comp:
        st.markdown("**Concordancia entre la IA y la docente** (solo producciones verificadas)")
        st.json({k: (None if v is None else round(v, 2) if isinstance(v, float) else v) for k, v in comp.items()})
        st.caption("Kappa de Cohen: valores cercanos a 1 indican alta concordancia. Con pocas producciones es solo orientativo.")
    else:
        st.info("Verificá producciones para calcular la concordancia.")
    if not df.empty:
        salida = df.copy()
        salida["estrategias"] = salida["estrategias"].apply(";".join)
        salida["dificultades"] = salida["dificultades"].apply(";".join)
        st.download_button("Descargar tabla (CSV)", salida.to_csv(index=False).encode("utf-8"), "analisis.csv", "text/csv")
        sin_imagen = [{k: v for k, v in i.items() if k != "imagen"} for i in ss["items"]]
        st.download_button("Descargar datos (JSON)", json.dumps(sin_imagen, ensure_ascii=False, indent=2).encode("utf-8"), "analisis.json", "application/json")
        st.download_button("Descargar informe (Markdown)", est.informe_markdown(ss["items"], ss["esquema"], ss["intervenciones"]).encode("utf-8"), "informe.md", "text/markdown")
    st.divider()
    if st.button("🗑️ Borrar todos los datos de la sesión"):
        for k in ("items", "intervenciones"):
            ss.pop(k, None)
        st.rerun()
