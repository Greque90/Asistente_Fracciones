import io
import os
import sys
from types import SimpleNamespace

import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import analisis
import estadisticas as est
from esquema import esquema_por_defecto, validar_esquema
from imagenes import preparar_imagen

ESQ = esquema_por_defecto()


def jpeg(ancho=200, alto=100):
    buf = io.BytesIO()
    Image.new("RGB", (ancho, alto), "white").save(buf, "JPEG")
    return buf.getvalue()


def test_esquema_valido():
    assert validar_esquema(ESQ) == []
    assert validar_esquema({"enunciado": "x"})  # faltan claves


def test_extraer_json_con_bloque_de_codigo():
    assert analisis.extraer_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert analisis.extraer_json('Resultado: {"a": 2} fin') == {"a": 2}
    with pytest.raises(ValueError):
        analisis.extraer_json("sin json")


def test_normalizar_marca_codigos_desconocidos_y_sin_cita():
    crudo = {
        "transcripcion": "1/4", "respuesta_fraccion": " 1 / 4 ", "tiene_justificacion": True,
        "estrategias": [{"codigo": "s1", "cita": "cuatro partes", "certeza": "alta"},
                        {"codigo": "S99", "cita": "x", "certeza": "alta"}],
        "dificultades": [{"codigo": "D1", "cita": "", "certeza": "alta"}],
    }
    r = analisis.normalizar_resultado(crudo, ESQ)
    assert r["respuesta_fraccion"] == "1/4"
    assert [e["codigo"] for e in r["estrategias"]] == ["S1"]
    assert r["dificultades"][0]["certeza"] == "baja"  # sin cita -> certeza baja
    assert r["requiere_revision"] is True
    assert "S99" in r["motivo_revision"]


def test_analizar_imagen_con_cliente_simulado():
    llamadas = {}

    def crear(**kwargs):
        llamadas.update(kwargs)
        texto = '{"transcripcion":"4/1","respuesta_fraccion":"4/1","tiene_justificacion":false,"menciona_partes_iguales":false,"estrategias":[],"dificultades":[{"codigo":"D2","cita":"4/1","certeza":"media","hipotesis":"h"}]}'
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=texto)])

    cliente = SimpleNamespace(messages=SimpleNamespace(create=crear))
    r = analisis.analizar_imagen(cliente, "modelo-x", jpeg(), ESQ)
    assert r["respuesta_fraccion"] == "4/1" and r["dificultades"][0]["codigo"] == "D2"
    assert llamadas["model"] == "modelo-x"
    assert llamadas["messages"][0]["content"][0]["type"] == "image"
    assert "No transcribas nombres" in llamadas["system"] or "nombres de personas" in llamadas["system"]


def test_cohen_kappa():
    assert est.cohen_kappa(["a", "b", "a"], ["a", "b", "a"]) == 1.0
    k = est.cohen_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"])
    assert k == pytest.approx(0.0)
    assert est.cohen_kappa([], []) is None


def _item(i, lote, ia, doc=None):
    return {"id": i, "lote": lote, "imagen": b"", "ia": analisis.normalizar_resultado(ia, ESQ), "docente": doc, "error": None}


def test_concordancia_y_resumen():
    ia1 = {"respuesta_fraccion": "4/1", "tiene_justificacion": True, "estrategias": [{"codigo": "S1", "cita": "c", "certeza": "alta"}],
           "dificultades": [{"codigo": "D2", "cita": "c", "certeza": "alta"}]}
    ia2 = {"respuesta_fraccion": "1/4", "tiene_justificacion": False, "estrategias": [], "dificultades": []}
    doc1 = {"respuesta_fraccion": "4/1", "tiene_justificacion": True, "menciona_partes_iguales": False,
            "estrategias": ["S1"], "dificultades": ["D2", "D5"], "verificado": True}
    items = [_item("A-P01", "L1", ia1, doc1), _item("A-P02", "L2", ia2)]
    comp = est.comparar_ia_docente(items)
    assert comp["n_verificadas"] == 1
    assert comp["acuerdo_dificultades"] == pytest.approx(0.5)
    resumen = est.resumen_para_ia(items)
    assert resumen["n"] == 2 and resumen["dificultades_frecuencia"]["D2"] == 1
    assert "imagen" not in str(resumen)
    md = est.informe_markdown(items, ESQ)
    assert "Respuestas por lote" in md and "hipótesis" in md


def test_preparar_imagen_recorta_y_rota():
    img, datos = preparar_imagen(jpeg(200, 100), rotacion=90, recorte={"arriba": 10, "abajo": 10, "izquierda": 0, "derecha": 0})
    # 200x100 rotado 90° queda 100x200; quitar 10% arriba y abajo deja 100x160
    assert img.size == (100, 160)
    assert datos[:2] == b'\xff\xd8'  # JPEG


def test_app_modo_demostracion():
    """Prueba de humo: la app carga, analiza en modo demo y calcula resultados."""
    from streamlit.testing.v1 import AppTest

    raiz = os.path.dirname(os.path.dirname(__file__))
    at = AppTest.from_file(os.path.join(raiz, "app.py"), default_timeout=30)
    at.session_state["items"] = [
        {"id": f"L1-P0{n}", "lote": "L1", "imagen": jpeg(), "ia": None, "error": None, "docente": None} for n in range(1, 5)
    ]
    at.run()
    assert not at.exception
    analizar = [b for b in at.button if b.label == "Analizar pendientes"][0]
    analizar.click().run()
    assert not at.exception
    assert all(i["ia"] for i in at.session_state["items"])
    generar = [b for b in at.button if b.label == "Generar propuesta de puesta en común"][0]
    generar.click().run()
    assert not at.exception
    assert "Modo demostración" in at.session_state["intervenciones"]
