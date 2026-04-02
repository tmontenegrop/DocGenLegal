📑 BLUEPRINT: DocGen Legal Pro (MVP 1.1)
1. Visión del Producto
Herramienta SaaS para el sector LegalTech que automatiza la generación masiva de documentos (.docx) a partir de una base de datos Excel. El diferencial competitivo es la Validación Previa (UX de confianza) y el enfoque en Nicho Legal (RUT, Fechas, Nombres).

2. Stack Tecnológico Actual
Backend: Python 3.9+ con FastAPI.

Librerías Críticas: pandas, openpyxl (lectura Excel), docxtpl (motor de plantillas Jinja2 para Word).

Frontend: HTML5 + Tailwind CSS (vía CDN) + FontAwesome.

Infraestructura: Render (Plan Free - 512MB RAM).

3. Lógicas y Reglas Implementadas
Drag & Drop: Interfaz interactiva con feedback visual (cambio de color y nombre de archivo).

Validación de Datos (Fase Previa): * Ruta /validar-excel/ que devuelve un JSON con alertas.

Reglas: Campos vacíos, formato RUT chileno, detección de números en nombres.

Gestión de Memoria (Anti-Crash):

Límite estricto de 100 filas por proceso.

Uso de BackgroundTasks para borrar archivos temporales tras la descarga.

Reutilización de buffers (io.BytesIO) para no saturar la RAM.

4. Estructura de Archivos Necesaria
app/main.py: Contiene las rutas de FastAPI (/, /validar-excel/, /generar-zip/).

index.html: Interfaz única con Dashboard, zona de Drag&Drop y Tabla de Pre-visualización dinámica.

requirements.txt: fastapi, uvicorn, pandas, openpyxl, docxtpl, python-multipart.

5. Pendientes en la Hoja de Ruta (Roadmap)
Mapeo Dinámico: Permitir al usuario asignar qué columna del Excel corresponde a qué etiqueta {{ }} del Word.

Base de Datos: Implementar PostgreSQL para guardar historial de procesos.

Seguridad: Implementar sistema de login para cobrar por uso o suscripción.