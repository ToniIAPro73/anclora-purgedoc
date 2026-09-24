# ANCLORA PURGEDOC — MVP 1.0

Plataforma de purga documental real, privada y verificada para archivos PDF y DOCX con informe de auditoría criptográfico y modelo de acceso cerrado por lista blanca.

## Modelo de Acceso y Rutas

- `/`: Landing pública premium con explicación de capacidades reales (redacción física, OCR local spa+eng, spaCy NER + regex, verificación fail-closed, auditoría SHA-256).
- `/login`: Pantalla de autenticación dedicada por correo y contraseña, con botones sociales (Google y GitHub) visibles pero deshabilitados ("Próximamente").
- `/activate`: Activación de cuenta mediante token criptográfico de un solo uso entregado por un administrador.
- `/app`: Workspace protegido de PurgeDoc. Las sesiones y lotes efímeros sólo se inicializan tras autenticación.

## Características Principales
- **100% Procesamiento Privado**: Cero llamadas a APIs de LLM externas. Motor NER con spaCy (`es_core_news_sm`, `en_core_web_sm`) y reglas regex configurables en YAML (`backend/config/profiles/*.yaml`).
- **Perfiles Verticales Especializados**:
  - **RRHH / Nóminas**: DNI, NIE, SSN, IBAN, salarios, nombres, teléfonos y direcciones.
  - **Legal / Contratos**: CIF, DNI de otorgantes, autos judiciales, cláusulas y honorarios.
  - **Soporte Técnico / DevOps**: Direcciones IP, API keys, tokens JWT, emails y tickets.
- **Purga Física Real**:
  - En **PDF**: Eliminación física de comandos y streams mediante PyMuPDF (`apply_redactions`) con recolección de basura.
  - En **DOCX**: Saneamiento profundo de paquetes OOXML (`word/document.xml`, tablas, headers, footers y `core.xml`).
- **Verificación Fail-Closed**: Reinspección automática post-proceso. Si queda cualquier residuo, se bloquea la certificación de seguridad.
- **Auditoría Forense Criptográfica**: Exportación en PDF imprimible, JSON estructurado y CSV sin exponer datos en claro (hashing SHA-256).
- **Diseño & Accesibilidad**: Interfaz en español e inglés (ES/EN), modos Claro / Oscuro / Sistema (Oscuro por defecto), visor interactivo con bounding boxes sincronizados y accesibilidad WCAG 2.1 AA.
- **Seguridad & Gobernanza**: Hashing Argon2id, tokens JWT mediante cookies HttpOnly, rotación de invitaciones y gestión administrativa por CLI.

## Gestión Administrativa de Whitelist (CLI)

```bash
# Añadir invitación
python backend/scripts/manage_whitelist.py add --email usuario@empresa.com

# Listar invitaciones
python backend/scripts/manage_whitelist.py list

# Rotar token
python backend/scripts/manage_whitelist.py rotate --target usuario@empresa.com

# Revocar acceso
python backend/scripts/manage_whitelist.py revoke --target usuario@empresa.com
```

## Puesta en Marcha Local

### Requisitos del sistema
- Python 3.12 (mínimo 3.11), Node 20+ y Yarn 1.22.
- Tesseract OCR con los idiomas `spa` y `eng` (macOS: `brew install tesseract tesseract-lang`; Debian/Ubuntu: `apt-get install tesseract-ocr tesseract-ocr-spa tesseract-ocr-eng`).
- LibreOffice (`soffice`) es opcional: si no está, la vista previa DOCX usa un PDF generado con PyMuPDF.

### Configuración
Copia `backend/.env.example` y `frontend/.env.example` a `.env.local` (ficheros ignorados por Git, modo `0600`).

### Backend (desde la raíz del repositorio)
```bash
python3.12 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
PYTHONPATH=. uvicorn backend.server:app --host 127.0.0.1 --port 8001
```

### Frontend
```bash
cd frontend
yarn install --frozen-lockfile
REACT_APP_BACKEND_URL=http://localhost:8001 yarn start
```

### Ejecución de Pruebas
```bash
# Suite determinista (backend/pytest.ini aplica -n 2 con pytest-xdist)
PYTHONPATH=. python -c "from backend.fixtures_generator import generate_all_fixtures; generate_all_fixtures()"
PYTHONPATH=. pytest backend/tests \
  --ignore=backend/tests/test_api_e2e.py \
  --ignore=backend/tests/test_encrypted_ruleset_http.py \
  --ignore=backend/tests/security/test_sensitive_log_leakage.py

# Pruebas HTTP: con el backend arrancado en local
REACT_APP_BACKEND_URL=http://127.0.0.1:8001 PYTHONPATH=. pytest \
  backend/tests/test_api_e2e.py backend/tests/test_encrypted_ruleset_http.py \
  backend/tests/security/test_sensitive_log_leakage.py

# Frontend
cd frontend && CI=true yarn test --watchAll=false && yarn build
```
