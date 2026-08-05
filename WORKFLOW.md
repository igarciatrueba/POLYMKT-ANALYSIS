# Workflow de desarrollo (Claude Code)

Este repo tiene dos colaboradores trabajando en paralelo, cada uno con su propia sesión de Claude Code. Este documento define el flujo exacto que sigue Claude Code en este repo, para que ambos colaboradores sepan qué esperar y no haya sorpresas ni conflictos de push.

## Regla central

**Nunca se commitea ni se pushea directo a `main`.** Todo cambio pasa por una rama de feature y un Pull Request.

## Flujo paso a paso

1. **Antes de empezar una tarea**, Claude Code actualiza `main` localmente:
   ```
   git checkout main
   git pull origin main
   ```
2. **Crea una rama de feature** a partir de `main`, con prefijo según el tipo de trabajo:
   - `feature/<nombre>` — nueva funcionalidad (ej. `feature/leaderboard-ingestion`)
   - `fix/<nombre>` — corrección de bug
   - `docs/<nombre>` — solo documentación
   - `chore/<nombre>` — configuración, dependencias, tareas de mantenimiento
3. **Escribe el código** (o el documento) en esa rama.
4. **Commitea** con mensajes descriptivos centrados en el "por qué", siguiendo el estilo de commits de este repo. Cada commit incluye:
   ```
   Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
   ```
5. **Pushea automáticamente** esa rama a `origin` tras cada commit — sin pedir confirmación al usuario para el push en sí (el push a una rama de feature es de bajo riesgo, ya que no toca `main`).
6. **Abre un Pull Request** hacia `main` usando `gh pr create`, con una descripción clara de qué cambia y por qué, y un plan de test/verificación.
7. **No mergea el PR automáticamente.** El merge a `main` requiere revisión humana (del usuario o de su colaborador) — Claude Code nunca aprueba ni mergea sus propios PRs sin permiso explícito.
8. Si el PR necesita cambios tras revisión, Claude Code sigue commiteando y pusheando a la misma rama; el PR se actualiza solo.

## Por qué este flujo

Dos personas trabajando con Claude Code sobre el mismo repo, cada una en su propia sesión, pueden generar commits al mismo tiempo. Si ambas sesiones pushean directo a `main`, la segunda en pushear puede rebotar (non-fast-forward) o, peor, sobrescribir trabajo si se fuerza el push. Aislar cada tarea en su propia rama de feature elimina ese riesgo: cada colaborador trabaja en su carril, y `main` solo se mueve mediante PRs revisados y mergeados de forma consciente.

## CI

Este repo tiene GitHub Actions configurado. Los PRs deben pasar CI antes de mergear (cuando existan checks definidos — se irán añadiendo a medida que haya tests/lint que correr).

## Resumen rápido

| Acción | ¿Automática? |
|---|---|
| `git pull` de `main` antes de empezar | Sí |
| Crear rama de feature | Sí |
| Commit | Sí |
| Push de la rama de feature | Sí, automático |
| Crear PR | Sí, automático al terminar la tarea |
| Mergear PR a `main` | **No** — requiere aprobación humana |
| Push directo a `main` | **Nunca** |
