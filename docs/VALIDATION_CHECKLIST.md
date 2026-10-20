# Checklist de validación — carrera en los tests HTTP del backend

**Alcance:** el job `Backend tests` fallaba de forma intermitente en `HTTP tests against local backend` con `Failed to authenticate test session: 500`. El log del servidor (paso añadido en `8326924`) muestra `ResponseValidationError … IndexError: tuple index out of range` en `POST /api/auth/login`: con `-n 2` (xdist) dos workers reescriben la fila del usuario QA en el SQLite compartido mientras el servidor la lee. Se ejecutan esos tests HTTP en serie con `-n 0`, la opción que documenta `backend/pytest.ini`; `addopts` no se modifica.

## Comprobaciones ejecutadas

| Comprobación | Resultado |
| --- | --- |
| Causa raíz en el log del servidor de CI | `IndexError` al serializar `UserRow` en el login |
| Reproducción local con entorno de CI y `-n 2` | PASS — la carrera es intermitente |
| Integridad del diff | `git diff --check` |

## Verificación de GitHub

Pendiente: el job `Backend tests` debe quedar en verde en el siguiente run de `development`.

## Verificación visual

No aplica: solo workflow de CI.

## Promoción

No solicitada hasta que el CI esté en verde.
