from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from docxtpl import DocxTemplate
import pandas as pd
import io
import os
import uuid
import shutil

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

@app.get("/", response_class=HTMLResponse)
async def home():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

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

    # --- NUEVA VALIDACIÓN DE CALIDAD ---
    # Revisamos si hay valores nulos en el Excel
    if df.isnull().values.any():
        columnas_con_error = df.columns[df.isnull().any()].tolist()
        return {
            "error": "Datos incompletos",
            "detalle": f"Faltan datos en las columnas: {', '.join(columnas_con_error)}. Por favor, revisa tu Excel."
        }, 400

    # 3. Crear carpeta única para el lote
    lote_id = str(uuid.uuid4())[:8]
    ruta_lote = os.path.join(OUTPUT_DIR, lote_id)
    os.makedirs(ruta_lote, exist_ok=True)

    # 4. Bucle de generación
    for index, fila in df.iterrows():
        # Usamos BytesIO para no re-leer el archivo del disco en cada vuelta
        doc = DocxTemplate(io.BytesIO(template_bytes))
        contexto = fila.to_dict()
        doc.render(contexto)

        nombre_cliente = str(fila.get('nombre_cliente', f"Doc_{index}")).replace(" ", "_")
        nombre_final = f"Contrato_{nombre_cliente}.docx"

        ruta_final = os.path.join(ruta_lote, nombre_final)
        doc.save(ruta_final)

    # 5. Crear el ZIP
    nombre_zip_base = os.path.join(OUTPUT_DIR, f"Paquete_{lote_id}")
    ruta_zip_final = shutil.make_archive(nombre_zip_base, 'zip', ruta_lote)

    # === LA CLAVE DEL ÉXITO: RESPUESTA DIRECTA ===
    # En lugar de un JSON, enviamos el archivo físico directamente
    return FileResponse(
        path=ruta_zip_final,
        filename="documentos_legales.zip",
        media_type='application/zip'
    )