# Smart Money Scoring — Diseño (Fase 2)

## Contexto

La Fase 1 dejó en la base de datos los cuatro flujos de ingesta funcionando: mercados activos (`markets`), ranking de top traders (`trader_rankings`), posiciones abiertas de esos traders (`positions`) y snapshots de precio/order book (`market_price_snapshots`).

Esta fase calcula el **Smart Money Signal**: el primero de los dos componentes del score de recomendación definido en `docs/design.md`. El segundo componente (Edge Signal) y su combinación ponderada (`w1`/`w2`) son fases posteriores.

## Objetivo

Para cada mercado activo y cada lado (Yes/No), cuantificar cuánto capital de los top traders está posicionado en ese lado, normalizado a una escala 0-100 comparable entre mercados, y persistirlo como snapshot histórico para permitir la calibración futura de pesos vía backtesting.

## Fórmula

Para cada mercado y lado:

```
capital_lado = Σ value_usd  de las posiciones que cumplen:
                 - pertenecen al snapshot más reciente de `positions` (captured_at == max)
                 - su wallet_address está en el cohorte top-N más reciente de `trader_rankings`
                 - su condition_id existe en `markets` y está activo
                 - su outcome coincide exactamente con el string literal del lado ("Yes" / "No")

score = (capital_lado / max_capital_del_batch) × 100
```

### Normalización anclada en cero

La normalización divide por el máximo del lote, **no** por el rango min-max. Esto es deliberado:

- Con min-max, el mercado con menor capital (pero con cobertura real) obtendría score 0, indistinguible de un mercado sin ninguna cobertura. La serie histórica resultante no sería calibrable.
- Con anclaje en cero, `score = 0` significa literalmente "cero capital de smart money", y la escala se lee como "porcentaje del mayor capital smart money detectado en este ciclo".

**Caso borde `max_capital_del_batch == 0`**: si ningún mercado del lote tiene capital de top traders, todos los scores son 0 y no se realiza división. No hay división por cero posible.

**Caso borde de un solo mercado con cobertura**: ese mercado obtiene score 100 (es su propio máximo). Esto es correcto y esperado bajo esta definición.

### Por qué el scoping al snapshot más reciente es crítico

Tanto `positions` como `trader_rankings` son tablas **append-only**: cada ciclo de ingesta inserta un lote nuevo con su propio `captured_at`, preservando el histórico (requisito de `docs/design.md` para el backtesting futuro).

Por tanto, una consulta ingenua del tipo `SELECT ... FROM positions WHERE condition_id = X` sumaría **todos los snapshots jamás tomados**, inflando el capital proporcionalmente al número de ciclos ejecutados. Este es exactamente el defecto que la revisión final de Fase 1 detectó en `ingest_positions_for_top_traders` y que se corrigió allí.

El cálculo debe filtrar explícitamente por `captured_at == (SELECT max(captured_at) FROM positions)`.

**Fuente autoritativa del cohorte**: el conjunto de wallets se determina por el snapshot más reciente de `trader_rankings` (filtrado por `category` y `time_period` de la configuración, ordenado por `rank`, limitado a `settings.top_n_traders`) — exactamente la misma lógica que ya usa `ingest_positions_for_top_traders`. Por construcción ambos conjuntos coinciden, pero `trader_rankings` es la fuente de verdad para evitar que el implementador invente un join distinto.

## Alcance y exclusiones

- **Solo mercados binarios Yes/No.** El esquema de `Market` de la Fase 1 solo contempla `token_id_yes`/`token_id_no`. Los mercados multi-resultado quedan fuera de esta fase.
- **Coincidencia exacta de outcome.** `Position.outcome` viene literal de la Data API de Polymarket; `MarketPriceSnapshot.outcome` lo escribe nuestro propio código. Ambos usan los literales `"Yes"` y `"No"`. El cálculo asume coincidencia exacta de esos strings. Si la API cambiara a otra capitalización o variante, la cobertura caería silenciosamente a cero en lugar de fallar — por eso un test debe fijar explícitamente los literales.
- **Mercados desconocidos se omiten.** Un top trader puede tener posición en un mercado que la barrida de Gamma no devolvió (resuelto, o filtrado). Esos `condition_id` se omiten del lote de scoring: el lote es "mercados activos conocidos", no "todo lo que algún trader tenga".
- **Cobertura cero se persiste igualmente.** Los mercados activos sin ninguna posición de top traders generan fila con `score = 0` y `has_coverage = False`. Así la fase del Score combinado puede aplicar su regla de exclusión sin re-consultar `positions`, y el histórico queda completo para backtesting.

## Esquema

Tabla nueva `smart_money_scores`, siguiendo el patrón **append-only** de `trader_rankings` y `market_price_snapshots` (nunca upsert, a diferencia de `markets`):

| Columna | Tipo | Notas |
|---|---|---|
| `id` | BigInteger, PK autoincremental | |
| `condition_id` | String(80), not null | Referencia lógica a `markets.condition_id` |
| `outcome` | String(16), not null | `"Yes"` o `"No"` |
| `capital_usd` | Numeric(18,2), not null | Capital agregado bruto antes de normalizar |
| `score` | Numeric(6,2), not null | 0-100 normalizado |
| `has_coverage` | Boolean, not null | False cuando ningún top trader está posicionado |
| `trader_count` | Integer, not null | Cuántos top traders distintos están en ese lado |
| `captured_at` | DateTime(timezone=True), not null | Un único valor por ejecución del cálculo |

`trader_count` no es estrictamente necesario para la fórmula (que pondera por capital, no por conteo), pero es información valiosa para el frontend (la vista de detalle por mercado del diseño muestra "qué top traders están posicionados y con cuánto capital") y para diagnosticar si un score alto viene de una sola ballena o de consenso amplio.

## Integración con el scheduler

El scoring se encadena al job existente de `position_ingestion` (20 minutos), inmediatamente después de persistir las posiciones y dentro de la misma transacción. El Smart Money Signal solo cambia cuando cambian esas posiciones, y este encadenamiento evita que dos jobs concurrentes calculen contra ciclos distintos.

`run_smart_money_scoring()` queda disponible para ejecución manual, pero el scheduler llama al cálculo desde `run_position_ingestion()` tras el `flush` de posiciones. Si la ingesta o el scoring falla, la transacción completa se revierte y no queda un score desincronizado.

Cada ingesta registra además un lote en `position_ingestion_batches`, incluso cuando ningún trader tiene posiciones. Así un ciclo vacío reemplaza correctamente la cobertura anterior en vez de reutilizar para siempre el último lote no vacío.

## Testing

- Test del cálculo de capital agregado con posiciones sintéticas conocidas, verificando la suma ponderada por `value_usd`.
- Test de que solo se consideran las posiciones del snapshot más reciente (insertar dos snapshots, verificar que el antiguo se ignora) — es el defecto de mayor riesgo, dado que ya ocurrió una vez en Fase 1.
- Test de que solo se consideran wallets del cohorte top-N actual.
- Test de la normalización: dos mercados con capitales conocidos (ej. $500k y $50) producen scores 100 y 0.01 respectivamente, no 100 y 0.
- Test del caso `max == 0` (ningún mercado con cobertura): todos los scores 0, sin excepción.
- Test de cobertura cero: mercado activo sin posiciones genera fila con `has_coverage=False`, `score=0`.
- Test de que un `condition_id` presente en `positions` pero ausente de `markets` se omite.
- Test de coincidencia exacta de los literales `"Yes"`/`"No"`.

## Riesgos conocidos

- **Reescalado por ciclo.** El score es relativo al máximo de cada lote, así que un mercado cuyo capital no cambió puede variar de score porque una ballena entró en *otro* mercado. Esto es inherente a cualquier normalización relativa y es aceptable para un score comparativo, pero significa que la serie histórica de `score` no es una serie absoluta. Por eso se persiste también `capital_usd` (bruto, sin normalizar): el backtesting futuro puede recalcular la normalización que prefiera sobre el dato crudo.
- **Cobertura escasa.** Tras el fix de Fase 1, las posiciones provienen solo del cohorte top-N actual. Es probable que solo unas decenas de mercados tengan cobertura, frente a miles de mercados activos. Esto es correcto por diseño (el pilar de la recomendación es la coincidencia de smart money), pero conviene monitorizar el ratio de cobertura vía el logging del job.
