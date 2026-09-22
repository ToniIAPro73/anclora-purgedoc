# GARANTÍAS DE PURGA Y REDACCIÓN REAL

## 1. Diferencia frente a Ocultación Visual
Una caja negra superpuesta mediante CSS, canvas, anotaciones visuales o resaltados en procesadores de texto **NO ES REDACCIÓN SEGURA**. El texto permanece subyacente y es trivialmente recuperable mediante copy-paste o inspección del código binario.

## 2. Garantía Técnica en PDF
1. PyMuPDF localiza los rectángulos exactos en las corrientes del PDF.
2. Se inyecta una anotación de redacción física (`add_redact_annot`).
3. Se invoca `apply_redactions()`, que físicamente sobrescribe y elimina los caracteres y comandos de dibujado de la página.
4. Se sanea la cabecera Info y metadatos XML (Author, Subject, Producer, ModDate).
5. Se guarda con `garbage=4`, `deflate=True`, `clean=True`.

## 3. Garantía Técnica en DOCX (OOXML)
1. Modificación de párrafos, tablas y cabeceras/pies.
2. Inspección profunda de todas las partes XML del contenedor ZIP (`word/document.xml`, `core.xml`, etc.).
3. Eliminación o sustitución por marca segura `[REDIGIDO]`.

## 4. Política Fail-Closed
El motor reabre el archivo generado y extrae su texto completo. Si alguna cadena aprobada sigue existiendo en el texto extraíble o metadatos, el proceso **ABORTA** y la descarga segura queda bloqueada.
