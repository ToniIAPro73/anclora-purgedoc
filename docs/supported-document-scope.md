# ALCANCE DE FORMATOS Y ESTRUCTURAS SOPORTADAS

## Soportado en MVP 1.0
- **PDF Nativo**: Documentos PDF generados digitalmente con capa de texto seleccionable y vectorial.
- **DOCX OOXML**: Documentos de Microsoft Word modernos (.docx) que contengan texto en cuerpo principal, tablas, cabeceras, pies de página y propiedades del paquete.

## Limitaciones Explícitas del MVP
- **PDFs escaneados (solo imagen)**: Requieren motor OCR local. Si un PDF no tiene capa de texto, el sistema rechaza el archivo para evitar una falsa sensación de seguridad.
- **Contenido Dinámico / OLE**: Objetos incrustados como hojas Excel dentro de Word no se procesan en profundidad en el MVP.
