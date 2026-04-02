from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse  # Para enviar el archivo al navegador
from docxtpl import DocxTemplate
import pandas as pd
import io
import os
import uuid
import shutil  # La herramienta para crear el ZIP

app = FastAPI(title="DocGen Legal Pro")

# Configuración de Seguridad (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = "salida"
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.post("/generar-documentos/")
async def generar_legal(
        excel_file: UploadFile = File(...),
        template_file: UploadFile = File(...)
):
    # 1. Leer archivos
    excel_bytes = await excel_file.read()
    template_bytes = await template_file.read()

    # 2. Cargar datos
    df = pd.read_excel(io.BytesIO(excel_bytes))

    # 3. Crear carpeta única para el lote
    lote_id = str(uuid.uuid4())[:8]
    ruta_lote = os.path.join(OUTPUT_DIR, lote_id)
    os.makedirs(ruta_lote, exist_ok=True)

    archivos_generados = []

    # 4. Bucle de generación
    for index, fila in df.iterrows():
        doc = DocxTemplate(io.BytesIO(template_bytes))
        contexto = fila.to_dict()
        doc.render(contexto)

        # Nombre personalizado por cliente
        nombre_cliente = str(fila.get('nombre_cliente', f"Doc_{index}")).replace(" ", "_")
        nombre_final = f"Contrato_{nombre_cliente}.docx"

        ruta_final = os.path.join(ruta_lote, nombre_final)
        doc.save(ruta_final)
        archivos_generados.append(nombre_final)

    # === AQUÍ VA LA LÓGICA DEL ZIP ===
    nombre_zip = f"Paquete_{lote_id}"
    # shutil.make_archive crea el archivo .zip físicamente en la carpeta 'salida'
    ruta_zip_generado = shutil.make_archive(
        os.path.join(OUTPUT_DIR, nombre_zip),  # Dónde y cómo se llamará
        'zip',  # Formato
        ruta_lote  # Qué carpeta queremos comprimir
    )

    # Retornamos el link para que el abogado haga clic
    return {
        "estado": "Éxito",
        "total_archivos": len(archivos_generados),
        "descarga_zip": f"http://127.0.0.1:8000/descargar/{nombre_zip}.zip"
    }


# ESTE ES EL NUEVO "PASILLO" DE DESCARGA
@app.get("/descargar/{nombre_archivo}")
async def descargar_archivo(nombre_archivo: str):
    ruta_completa = os.path.join(OUTPUT_DIR, nombre_archivo)

    if os.path.exists(ruta_completa):
        return FileResponse(
            path=ruta_completa,
            filename=nombre_archivo,
            media_type='application/zip'
        )
    return {"error": "Archivo no encontrado"}

from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
async def home():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()