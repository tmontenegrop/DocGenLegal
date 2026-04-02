from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from docxtpl import DocxTemplate
import pandas as pd
import io
import os
import uuid
import shutil
import re

app = FastAPI(title="DocGen Legal Pro - MVP")

# --- CONFIGURACIÓN ---
OUTPUT_DIR = "salida"
os.makedirs(OUTPUT_DIR, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- UTILIDADES DE VALIDACIÓN ---
def validar_rut(rut):
    # Limpia y valida formato básico de RUT
    rut = str(rut).replace(".", "").replace("-", "").upper()
    return bool(re.match(r"^\d{7,8}[0-9K]$", rut))


# --- RUTAS ---

@app.get("/", response_class=HTMLResponse)
async def home():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/validar-excel/")
async def validar_excel(excel_file: UploadFile = File(...)):
    """Lee el Excel y devuelve los datos con alertas de error"""
    try:
        content = await excel_file.read()
        df = pd.read_excel(io.BytesIO(content))

        columnas = df.columns.tolist()
        filas_analizadas = []

        # Analizamos fila por fila
        for index, fila in df.iterrows():
            datos_fila = fila.fillna("").to_dict()
            alertas = {}

            for col, valor in datos_fila.items():
                val_str = str(valor).strip()
                col_lower = col.lower()

                # Regla 1: Campos vacíos
                if val_str == "":
                    alertas[col] = "Campo vacío"

                # Regla 2: Validación de RUT (si la columna dice 'rut')
                elif "rut" in col_lower and not validar_rut(val_str):
                    alertas[col] = "RUT inválido"

                # Regla 3: Nombres (si la columna dice 'nombre' y tiene números)
                elif "nombre" in col_lower and any(char.isdigit() for char in val_str):
                    alertas[col] = "Nombre con números"

            filas_analizadas.append({
                "id": index + 2,  # Corresponde a la fila en Excel (contando encabezado)
                "datos": datos_fila,
                "alertas": alertas
            })

        return {"columnas": columnas, "filas": filas_analizadas}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al leer Excel: {str(e)}")


@app.post("/generar-zip/")
async def generar_zip(excel_file: UploadFile = File(...), template_file: UploadFile = File(...)):
    """Procesa los documentos y entrega el ZIP directo"""
    try:
        excel_bytes = await excel_file.read()
        template_bytes = await template_file.read()
        df = pd.read_excel(io.BytesIO(excel_bytes))

        lote_id = str(uuid.uuid4())[:8]
        ruta_lote = os.path.join(OUTPUT_DIR, lote_id)
        os.makedirs(ruta_lote, exist_ok=True)

        for index, fila in df.iterrows():
            doc = DocxTemplate(io.BytesIO(template_bytes))
            doc.render(fila.to_dict())

            # Nombre de archivo basado en columna 'nombre_cliente' o índice
            nombre = str(fila.get('nombre_cliente', f"Documento_{index + 1}")).replace(" ", "_")
            ruta_doc = os.path.join(ruta_lote, f"Contrato_{nombre}.docx")
            doc.save(ruta_doc)

        # Crear el comprimido
        base_zip = os.path.join(OUTPUT_DIR, f"Paquete_{lote_id}")
        ruta_zip_final = shutil.make_archive(base_zip, 'zip', ruta_lote)

        return FileResponse(path=ruta_zip_final, filename="Documentos_Legales.zip", media_type='application/zip')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))