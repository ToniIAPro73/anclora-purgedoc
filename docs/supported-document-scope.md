# ALCANCE DE FORMATOS Y ESTRUCTURAS SOPORTADAS

## Soportado en MVP 1.0
- **PDF Nativo**: Documentos PDF generados digitalmente con capa de texto seleccionable y vectorial.
- **PDF Escaneado (Raster-Only)**: Procesamiento mediante motor Tesseract OCR local integrado (sin servicios externos), obteniendo cajas de texto fiables y destruyendo físicamente los píxeles de la imagen subyacente.
- **DOCX OOXML**: Documentos de Microsoft Word modernos (.docx) que contengan texto en cuerpo principal, tablas, cabeceras, pies de página y propiedades del paquete.

## Limitaciones Explícitas del MVP
- **Contenido Dinámico / OLE**: Objetos incrustados como hojas Excel dentro de Word no se procesan en profundidad en el MVP.
