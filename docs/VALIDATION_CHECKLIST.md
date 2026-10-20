# Checklist de validación — diagnóstico del job Backend tests

**Alcance:** el job `Backend tests` falla en `HTTP tests against local backend` con `Failed to authenticate test session: 500` sobre el commit `fb48313` (solo cambia un `.md`). El mismo código pasa al relanzar el CI de `47f56bb` y pasa en local con el entorno de CI. Se añade un paso `if: failure()` que imprime `uvicorn.log` para ver la causa real del 500.

## Comprobaciones ejecutadas

| Comprobación | Resultado |
| --- | --- |
| Reproducción local con entorno de CI (tests deterministas + HTTP e2e) | PASS — 103 y 8 tests |
| Rerun de CI en `47f56bb` | PASS |
| Rerun de CI en `fb48313` (2 intentos) | FAIL |

## Verificación de GitHub

Pendiente: leer el log del servidor en el siguiente run de `development`.

## Verificación visual

No aplica: solo workflow de CI.

## Promoción

No solicitada.
