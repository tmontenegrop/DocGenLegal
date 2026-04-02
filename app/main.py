from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from docxtpl import DocxTemplate
import pandas as pd
import io
import os
import uuid
import shutil
import re

app = FastAPI(title="DocGen Legal Pro - Estable")

# --- CONFIGURACIÓN DE RUTAS ---
OUTPUT_DIR = "temp_output"
if os.path.exists(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR)  # Limpieza al arrancar
os.makedirs(OUTPUT_DIR, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- UTILIDADES ---
def limpiar_carpeta(ruta: str):
    """Función para borrar archivos temporales después de la descarga"""
    if os.path.exists(ruta):
        shutil.rmtree(ruta)


def validar_rut(rut):
    rut = str(rut).replace(".", "").replace("-", "").upper()
    return bool(re.match(r"^\d{7,8}[0-9K]$", rut))


# --- RUTAS ---

@app.get("/", response_class=HTMLResponse)
async def home():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/validar-excel/")
async def validar_excel(excel_file: UploadFile = File(...)):
    try:
        content = await excel_file.read()
        df = pd.read_excel(io.BytesIO(content))

        # LÍMITE DE FILAS PARA ESTABILIDAD
        if len(df) > 100:
            return {"error": "Límite excedido",
                    "detalles": ["El sistema gratuito soporta hasta 100 filas por vez."]}, 400

        columnas = df.columns.tolist()
        filas_analizadas = []

        for index, fila in df.iterrows():
            datos_fila = fila.fillna("").to_dict()
            alertas = {}
            for col, valor in datos_fila.items():
                val_str = str(valor).strip()
                col_l = col.lower()
                if val_str == "":
                    alertas[col] = "Vacío"
                elif "rut" in col_l and not validar_rut(val_str):
                    alertas[col] = "RUT Inválido"

            filas_analizadas.append({"id": index + 2, "datos": datos_fila, "alertas": alertas})

        return {"columnas": columnas, "filas": filas_analizadas}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/generar-zip/")
async def generar_zip(background_tasks: BackgroundTasks, excel_file: UploadFile = File(...),
                      template_file: UploadFile = File(...)):
    lote_id = str(uuid.uuid4())[:8]
    ruta_lote = os.path.join(OUTPUT_DIR, lote_id)

    try:
        excel_bytes = await excel_file.read()
        template_bytes = await template_file.read()
        df = pd.read_excel(io.BytesIO(excel_bytes))

        if len(df) > 100:
            raise HTTPException(status_code=400, detail="Máximo 100 filas.")

        os.makedirs(ruta_lote, exist_ok=True)
        template_io = io.BytesIO(template_bytes)

        for index, fila in df.iterrows():
            template_io.seek(0)
            doc = DocxTemplate(template_io)
            # Convertimos datos a strings limpios para la plantilla
            contexto = {k: str(v) if pd.notna(v) else "" for k, v in fila.to_dict().items()}
            doc.render(contexto)

            # Nombre de archivo seguro
            nombre_sug = str(fila.get('nombre_cliente', f"Documento_{index + 1}"))
            nombre_f = re.sub(r'[^\w\s-]', '', nombre_sug).replace(" ", "_")
            doc.save(os.path.join(ruta_lote, f"{nombre_f}.docx"))

        # Crear ZIP
        ruta_zip_base = os.path.join(OUTPUT_DIR, f"Docs_{lote_id}")
        zip_final = shutil.make_archive(ruta_zip_base, 'zip', ruta_lote)

        # AGREGAR TAREA DE LIMPIEZA: Se ejecuta DESPUÉS de enviar el archivo
        background_tasks.add_task(limpiar_carpeta, ruta_lote)

        return FileResponse(path=zip_final, filename="Paquete_Legal.zip", media_type='application/zip')

    except Exception as e:
        if os.path.exists(ruta_lote): shutil.rmtree(ruta_lote)
        raise HTTPException(status_code=500, detail=str(e))