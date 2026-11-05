# Asistente docente para el análisis didáctico de producciones sobre fracciones

Aplicación en Python y Streamlit que ayuda a una docente a **ordenar, clasificar y comparar** producciones
escritas de estudiantes (fotografías de cuadernos), a **reconocer dificultades** y a **orientar las
intervenciones** de la puesta en común. Es la herramienta descripta en el informe final
*Inteligencia artificial y análisis didáctico de las producciones escritas sobre fracciones*.

> **Principio:** la IA propone, la docente decide. Toda clasificación lleva una cita de lo escrito, se marca
> la certeza y queda como hipótesis hasta que la docente la verifica.

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate          # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Para usar la API: definir `ANTHROPIC_API_KEY` (o pegarla en la barra lateral) y, si se desea, `ANTHROPIC_MODEL`
(por defecto `claude-sonnet-5-5`). El **modo demostración** funciona sin clave y no envía nada a ningún servicio.

## Flujo de trabajo (7 pestañas)

1. **Esquema.** Estrategias (S1–S7) y dificultades (D1–D5) editables, con preguntas abiertas por dificultad.
2. **Preparar.** Cargar fotografías, corregir la rotación y **recortar nombres** de estudiantes.
3. **Analizar.** La IA transcribe de manera literal (`[ilegible]` si no se lee) y clasifica con citas y certeza.
4. **Verificar.** La docente revisa cada producción, corrige y la marca como verificada.
5. **Resultados.** Tablas y gráficos por lote (antes y después de una discusión, entre cursos, etc.).
6. **Intervenciones.** Preguntas abiertas del esquema y propuesta de selección y secuenciación para la puesta en común.
7. **Exportar.** CSV, JSON, informe en Markdown y **concordancia IA–docente** (kappa de Cohen y acuerdo por conjuntos).

## Privacidad (importante)

- Los archivos y resultados viven **solo en la sesión** del navegador; no se escriben en disco.
- En modo API las imágenes **se envían al servicio** de la API. Antes: recortar nombres, contar con autorización de la
  institución y revisar la política de datos del proveedor. En Argentina rige la Ley 25.326 de Protección de Datos Personales.
- La propuesta de intervenciones se genera solo con un **resumen cuantitativo**, sin imágenes ni transcripciones.
- El botón *Borrar todos los datos de la sesión* limpia el estado.

## Límites conocidos

- Los diagnósticos de error son el punto débil de los modelos de visión, sobre todo con estudiantes que necesitan más ayuda.
- Los manuscritos poco legibles producen transcripciones parciales: revisar lo marcado con ⚠️.
- La concordancia con pocas producciones es solo orientativa. Conviene que **dos docentes** codifiquen una muestra.

## Estructura

```
app.py            interfaz Streamlit
analisis.py       prompts, llamada a la API, validación del JSON, modo demostración
estadisticas.py   tablas, comparación entre lotes, kappa de Cohen, informe
imagenes.py       orientación, recorte y reducción de tamaño
esquema.py        esquema de codificación por defecto y su validación
tests/            pruebas (pytest), incluida una prueba de humo de la app
```

Pruebas: `python -m pytest -q tests`
