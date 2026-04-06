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


import zipfile  # Asegúrate de tener este import arriba del todo


@app.post("/generar-zip/")
async def generar_zip(excel_file: UploadFile = File(...), template_file: UploadFile = File(...)):
    try:
        # 1. Cargar archivos a memoria
        excel_bytes = await excel_file.read()
        template_bytes = await template_file.read()
        df = pd.read_excel(io.BytesIO(excel_bytes))

        # 2. Crear un "Archivo Virtual" en memoria para el ZIP
        zip_buffer = io.BytesIO()
        template_io = io.BytesIO(template_bytes)

        # 3. Abrir el constructor de ZIP
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for index, fila in df.iterrows():
                template_io.seek(0)
                doc = DocxTemplate(template_io)

                # Limpiar datos para la plantilla
                contexto = {str(k): (str(v) if pd.notna(v) else "") for k, v in fila.to_dict().items()}
                doc.render(contexto)

                # Guardar el Word individual en memoria
                target_word = io.BytesIO()
                doc.save(target_word)
                target_word.seek(0)

                # Nombre de archivo seguro
                nombre_raw = str(fila.get('nombre_cliente', f"Documento_{index + 1}"))
                nombre_clean = re.sub(r'[^\w\s-]', '', nombre_raw).replace(" ", "_")

                # Agregar el Word al ZIP virtual
                zip_file.writestr(f"{nombre_clean}.docx", target_word.getvalue())

        # 4. Preparar el envío del ZIP final
        zip_buffer.seek(0)

        return StreamingResponse(
            io.BytesIO(zip_buffer.getvalue()),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=Contratos_Legales.zip"}
        )

    except Exception as e:
        print(f"ERROR EN GENERACIÓN: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# NOTA: Asegúrate de importar StreamingResponse de fastapi.responses arriba
# from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse