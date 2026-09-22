# MODELO DE PRIVACIDAD Y SEGURIDAD — ANCLORA PURGEDOC

## 1. Tratamiento de Datos
- **Procesamiento estrictamente local**: spaCy y PyMuPDF operan dentro del pod local de la aplicación.
- **Sin persistencia permanente**: No se almacenan documentos en bases de datos relacionales ni de objetos persistentes.
- **Hashing Criptográfico**: Para trazabilidad en auditoría, cada entidad detectada se anonimiza mediante SHA-256 (`sha256:...`).
- **Sanitización de Logs**: Se prohíbe taxativamente escribir cadenas sensibles o volcados de documentos en `stdout` o archivos de log.
