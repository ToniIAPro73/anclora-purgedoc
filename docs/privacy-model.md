# Modelo de Privacidad y Retención de Datos — Anclora Purgedoc

## 1. Principios Rectores
1. **Procesamiento 100 % Local Soberano**: Ningún dato, fragmento de texto, imagen o metadato abandona el servidor de procesamiento. No se utiliza ningún LLM externo, API de nube ni OCR remoto.
2. **Almacenamiento Efímero Estricto**: No existe base de datos permanente de documentos, texto ni usuarios. Todos los artefactos residen exclusivamente en `/tmp/anclora-purgedoc/{session_id}/` con TTL automático y borrado en cascada.
3. **Auditoría Criptográfica Zero-PII**: Los informes de auditoría (PDF, JSON, CSV) registran hashes SHA-256 (`sha256:...`) y metadatos saneados, garantizando la total ausencia de datos personales identificables o tokens sensibles en claro.

---

## 2. Política de Retención y Ciclo de Vida Temporal
| Tipo de Artefacto | Variable de Entorno | Valor por Defecto | Condición de Elegibilidad para Borrado |
| :--- | :--- | :--- | :--- |
| **Sesión de Usuario** | `SESSION_TTL_MINUTES` | 60 minutos | 60 min de **inactividad humana real** (los heartbeats SSE no renuevan el TTL) |
| **Documentos Fuente** | `SOURCE_DOCUMENT_TTL_MINUTES` | 15 minutos | Tras emisión exitosa de salida `verified` o expiración de sesión |
| **Artefactos Intermedios** | `INTERMEDIATE_ARTIFACT_TTL_MINUTES`| 15 minutos | Tras finalización de OCR, Deskew y previsualizaciones locales |
| **Salidas Verificadas** | `VERIFIED_OUTPUT_TTL_MINUTES` | 60 minutos | Disponible para descarga hasta el fin de la sesión o borrado manual |
| **Auditorías (PDF/JSON/CSV)** | `AUDIT_ARTIFACT_TTL_MINUTES` | 60 minutos | Disponible para descarga hasta el fin de la sesión o borrado manual |
| **Artefactos de Lote (ZIP)** | `BATCH_ARTIFACT_TTL_MINUTES` | 60 minutos | Disponible para descarga hasta el fin de la sesión o borrado manual |
| **Historial SSE / Event Bus**| `SSE_HISTORY_TTL_MINUTES` | 30 minutos | Purgado de colas y ring-buffer tras inactividad prolongada |

---

## 3. Acciones de Borrado Manual Inmediato
- **Eliminar Lote Ahora**: Destruye de inmediato los archivos temporales y memorias del lote seleccionado sin interferir con otros lotes de la misma sesión.
- **Eliminar Sesión Ahora**: Destruye en cascada todos los directorios temporales, documentos originales, salidas purgadas, registros de auditoría y canales SSE asociados a la sesión.

---

## 4. Alcance y Límites de la Eliminación
- La eliminación garantizada por Anclora Purgedoc aplica a todos los archivos, memorias y descriptores bajo su control en `/tmp/anclora-purgedoc/`.
- No constituye una garantía de destrucción física de bajo nivel sobre medios de almacenamiento sólido (SSD TRIM/wear leveling) ni sobre copias que el usuario ya haya descargado a su propio entorno o dispositivo.
