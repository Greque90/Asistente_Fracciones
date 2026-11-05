"""Preparación de imágenes: orientación, recorte para anonimizar y reducción de tamaño."""
from io import BytesIO

from PIL import Image, ImageOps

LADO_MAXIMO = 1568  # tamaño razonable para modelos de visión


def preparar_imagen(datos, rotacion=0, recorte=None):
    """Devuelve (imagen PIL, bytes JPEG).

    rotacion: 0, 90, 180 o 270 (sentido antihorario).
    recorte: dict con porcentajes a quitar: arriba, abajo, izquierda, derecha (0-90).
    """
    imagen = Image.open(BytesIO(datos))
    imagen = ImageOps.exif_transpose(imagen).convert("RGB")
    if rotacion % 360:
        imagen = imagen.rotate(rotacion, expand=True)
    if recorte:
        ancho, alto = imagen.size
        izq = int(ancho * recorte.get("izquierda", 0) / 100)
        der = ancho - int(ancho * recorte.get("derecha", 0) / 100)
        arr = int(alto * recorte.get("arriba", 0) / 100)
        aba = alto - int(alto * recorte.get("abajo", 0) / 100)
        if der - izq > 10 and aba - arr > 10:
            imagen = imagen.crop((izq, arr, der, aba))
    imagen.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
    salida = BytesIO()
    imagen.save(salida, format="JPEG", quality=85)
    return imagen, salida.getvalue()
