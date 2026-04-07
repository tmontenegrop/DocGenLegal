from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from docxtpl import DocxTemplate
import pandas as pd
import io
import os
import uuid
import shutil
import re
import zipfile

app = FastAPI(title="DocGen Legal Pro - Versión Final")

# --- CONFIGURACIÓN DE SEGURIDAD ---
# Aunque ahora trabajamos en memoria, mantenemos la limpieza inicial por orden
OUTPUT_DIR = "temp_storage"
if os.path.exists(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- UTILIDADES ---
def validar_rut(rut):
    """Limpia y valida formato básico de RUT chileno"""
    rut = str(rut).replace(".", "").replace("-", "").upper().strip()
    return bool(re.match(r"^\d{7,8}[0-9K]$", rut))


# --- RUTAS ---

@app.get("/", response_class=HTMLResponse)
async def home():
    """Sirve la interfaz principal"""
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Error: index.html no encontrado en la raíz.</h1>"


@app.post("/validar-excel/")
async def validar_excel(excel_file: UploadFile = File(...)):
    """Analiza el Excel y devuelve datos con alertas para la tabla previa"""
    try:
        content = await excel_file.read()
        df = pd.read_excel(io.BytesIO(content))

        # Límite de seguridad para evitar cuelgues de RAM
        if len(df) > 150:
            raise HTTPException(status_code=400, detail="Límite excedido: Máximo 150 filas.")

        columnas = df.columns.tolist()
        filas_analizadas = []

        for index, fila in df.iterrows():
            datos_fila = fila.fillna("").to_dict()
            alertas = {}
            for col, valor in datos_fila.items():
                val_str = str(valor).strip()
                col_l = col.lower()

                if val_str == "":
                    alertas[col] = "Campo vacío"
                elif "rut" in col_l and not validar_rut(val_str):
                    alertas[col] = "Formato RUT inválido"
                elif "nombre" in col_l and any(char.isdigit() for char in val_str):
                    alertas[col] = "Nombre contiene números"

            filas_analizadas.append({
                "id": index + 2,
                "datos": datos_fila,
                "alertas": alertas
            })

        return {"columnas": columnas, "filas": filas_analizadas}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al procesar Excel: {str(e)}")


@app.post("/generar-zip/")
async def generar_zip(excel_file: UploadFile = File(...), template_file: UploadFile = File(...)):
    """Genera múltiples Word y los comprime en un ZIP, todo en memoria RAM"""
    try:
        # 1. Lectura de archivos
        excel_bytes = await excel_file.read()
        template_bytes = await template_file.read()
        df = pd.read_excel(io.BytesIO(excel_bytes))

        if len(df) > 150:
            raise HTTPException(status_code=400, detail="Máximo 150 filas.")

        # 2. Preparación de Buffers (Memoria RAM)
        zip_buffer = io.BytesIO()
        template_io = io.BytesIO(template_bytes)

        # 3. Creación del ZIP
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for index, fila in df.iterrows():
                # Volver al inicio del archivo Word para cada renderizado
                template_io.seek(0)
                doc = DocxTemplate(template_io)

                # Preparar contexto (datos del Excel)
                # Convertimos todo a string y manejamos valores nulos
                contexto = {str(k): (str(v) if pd.notna(v) else "") for k, v in fila.to_dict().items()}

                # Renderizado SEGURO (no explota si faltan etiquetas)
                doc.render(contexto)

                # Guardar el resultado individual en memoria
                word_individual = io.BytesIO()
                doc.save(word_individual)
                word_individual.seek(0)

                # Definir nombre de archivo amigable
                nombre_cliente = str(fila.get('nombre_cliente', fila.get('nombre_trabajador', f"Doc_{index + 1}")))
                nombre_limpio = re.sub(r'[^\w\s-]', '', nombre_cliente).strip().replace(" ", "_")

                # Agregar al ZIP
                zip_file.writestr(f"{nombre_limpio}.docx", word_individual.getvalue())

        # 4. Retornar el archivo para descarga inmediata
        zip_buffer.seek(0)

        return StreamingResponse(
            io.BytesIO(zip_buffer.getvalue()),
            media_type="application/zip",
            headers={
                "Content-Disposition": "attachment; filename=Contratos_Generados_Pro.zip"
            }
        )

    except Exception as e:
        print(f"ERROR CRÍTICO EN GENERACIÓN: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fallo en el servidor: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)