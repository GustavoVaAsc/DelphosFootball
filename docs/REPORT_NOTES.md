# Memoria de hallazgos y decisiones metodológicas

## Contenido

1. [Propósito](#1-propósito)
2. [Ingesta de datos (`ingest`)](#2-ingesta-de-datos-ingest)
3. [Análisis exploratorio y selección de datos (`eda`)](#3-análisis-exploratorio-y-selección-de-datos-eda)
4. [Referencias internas](#4-referencias-internas)

---

## 1. Propósito

Este documento concentra en español los hallazgos empíricos, los tropiezos técnicos con los datos crudos, las alternativas evaluadas y las decisiones tomadas en cada etapa del proceso KDD de DelphosFootball, con el fin de redactar el reporte final en formato APA 7ª edición. La especificación normativa de software e ingeniería de modelos vive en [docs/ARCHITECTURE.md](ARCHITECTURE.md) y [docs/ML_ARCHITECTURE.md](ML_ARCHITECTURE.md), mientras que el seguimiento semanal del calendario vive en [docs/WORK_PLAN.md](WORK_PLAN.md).

## 2. Ingesta de datos (`ingest`)

### H-01. Inferencia automática de tipos en la carga de CSVs crudos

Durante la primera implementación de `ingest` sobre el dataset `davidcariboo/player-scores` (versión fijada `679`, `12` tablas y `7,497,433` filas), dejamos que `pandas` infiriera automáticamente los tipos de cada columna al convertir los CSV a Parquet. En la auditoría posterior detectamos que esa inferencia modificaba los valores originales sin avisar: cadenas con ceros a la izquierda como `"007"` pasaban a entero `7`, montos como `"700000.000"` en `transfers` cambiaban de representación frente a enteros como `"1000000"` en `players`, cadenas booleanas se convertían sin contrato explícito y posibles encabezados duplicados se renombraban silenciosamente. Además, cargar archivos grandes completos en memoria elevaba el consumo de RAM innecesariamente.

Reescribimos `ingest` con `pyarrow` por bloques de 16 MiB (pico medido de 703 MiB de RAM) de modo que todas las columnas de `ml/data/ingest/*.parquet` se guarden como texto exacto (`Arrow string`). Solo un campo vacío sin comillas pasa a nulo, mientras que `""` conserva el carácter de cadena vacía y centinelas como `"-"` quedan intactos para auditarse. Todo el tipado y saneamiento quedó delegado de forma exclusiva a la etapa `clean` ([ADR-012](ARCHITECTURE.md#adr-012-ingest-stores-source-columns-as-text-typing-happens-in-clean)).

## 3. Análisis exploratorio y selección de datos (`eda`)

Todos los conteos y pruebas de esta sección provienen de ejecutar `analysis/eda.py` sobre la versión `679`, cuyos resúmenes tabulares y seis figuras quedan en `analysis/output/eda/`.

### H-02. Ligas y torneos sin cobertura real en `appearances`

En descripciones previas del dataset de Transfermarkt suelen citarse alrededor de 44 competiciones y 14 ligas europeas. Al auditar `competitions` en la versión `679` encontramos `65` competiciones registradas y `31` filas etiquetadas con `type == 'domestic_league'`. Sin embargo, `17` de esas `31` ligas domésticas fueron añadidas entre 2024 y 2025 (`BRA1`, `ARG1`, `MLS1`, `JAP1`, `PL1`, `MEX1`, `TS1`, `RO1`, `C1`, `SER1`, `SE1`, `SA1`, `A1`, `NO1`, `KR1`, `RSK1` y `AUS1`) con partidos en `games` y `89,758` valuaciones de jugadores de campo, pero con `0` filas en `appearances`. Lo mismo ocurre en `UCOL` (fase principal de UEFA Conference League, `728` partidos y `0` apariciones) y en los torneos de selecciones `EURO`, `COPA` y `AFAC`.

Esta asimetría explicaba una anomalía aparente en la serie anual: el promedio global cayó de `24.12` apariciones por partido en 2023 a `14.79` en 2024. Al aislar las `14` ligas europeas de primera división que sí registran apariciones (`IT1`, `ES1`, `GB1`, `FR1`, `TR1`, `L1`, `NL1`, `PO1`, `BE1`, `RU1`, `GR1`, `SC1`, `UKR1` y `DK1`), la densidad real se mantuvo estable en `30.91` apariciones por partido en 2024 y `30.90` en 2025 (`analysis/output/eda/03a_coverage_by_season.csv` y `fig01_temporal_coverage.png`). Si hubiéramos filtrado `clean` solo por `type == 'domestic_league'`, miles de titulares de Liga MX, Brasileirão o liga polaca con algún partido aislado de copa internacional habrían entrado al modelo como si apenas hubieran jugado en el año. También detectamos que la UEFA Europa League (`EL`, `55,834` apariciones) y las rondas previas `ELQ` y `ECLQ` vienen clasificadas bajo `type == 'other'` con `sub_type` iniciado en `uefa_`, en lugar de `international_cup`.

Restringimos la población objetivo a clubes pertenecientes a la lista cerrada de esas `14` ligas europeas cubiertas entre las temporadas `2017` y `2025` (`2017/18` a `2025/26`, donde `game_lineups` ya mantiene al menos `34.61` registros por encuentro y la regla julio a junio coincide al `97.82%` con `games.season`). Para el historial deportivo de cada jugador sí sumamos sus minutos en esas 14 ligas, copas domésticas, supercopas y torneos UEFA identificados tanto por `international_cup` como por el prefijo `uefa_` en `sub_type` ([docs/ML_ARCHITECTURE.md](ML_ARCHITECTURE.md) §3.2).

### H-03. Ausencia de métricas específicas para porteros

En `players` aparecen `5,828` porteros (`72,205` filas en `player_valuations`, equivalentes a `4,604` arqueros distintos) y `586` registros con `position == 'Missing'`. Ninguna de las 12 tablas incluye atajadas, tiros recibidos, goles evitados ni salidas aéreas. Entre los porteros con al menos 450 minutos en el último año, el promedio es de `0.00014` goles por 90 minutos y `0.00273` asistencias por 90 minutos; su única señal defensiva disponible en el repositorio (`clean_sheet_rate`, obtenida al cruzar `club_games.opponent_goals == 0`) mide el desempeño colectivo del bloque defensivo. Conservarlos introduciría un grupo artificialmente separado en K-Means y sesgaría los coeficientes ofensivos en regresión, por lo que aplicamos un filtro de exclusión sobre `Goalkeeper` y `Missing`.

### H-04. Sesgo de frecuencia en valuaciones (Opción A frente a Opción B) y escala del valor de mercado

Evaluamos dos formas de definir cada fila de entrenamiento en el periodo `2017` a `2025` dentro de las 14 ligas: conservar las `235,594` actualizaciones crudas de `player_valuations` (Opción B) o tomar una fotografía anual por `(player_id, season)` en la última fecha de valuación del jugador dentro de esa temporada y agregar su rendimiento en los 365 días previos (Opción A, `107,456` filas antes del filtro de minutos). En la Opción B, el `30.86%` de los pares jugador-temporada recibe entre `3` y `6` revisiones en el mismo año (mediana `2`, percentil 90 de `3`, máximo `6`), lo que sobrepondera a figuras mediáticas y traspasos recientes e introduce autocorrelación serial entre filas separadas por pocas semanas. Adoptamos la Opción A ([docs/ML_ARCHITECTURE.md](ML_ARCHITECTURE.md) §3.3).

Respecto a la variable objetivo, `market_value_in_eur` en escala lineal presenta asimetría `7.44` y curtosis `84.76`. Al aplicar `log10(market_value_in_eur)`, la asimetría baja a `0.561` y la curtosis a `0.020` (`fig02_market_value_distribution.png`). Entre 2017 y 2025 el percentil 90 del valor de mercado pasó de `4.0` millones de EUR a `8.0` millones de EUR, razón por la cual la temporada debe controlarse explícitamente en la etapa de transformación.

### H-05. Piso de minutos, suavizado Empirical Bayes y elección de la función de error

Fijar un umbral alto de exposición como `>= 900` minutos deja `33,113` jugador-temporadas (`10,972` jugadores) y elimina el `30.1%` de las filas disponibles con `>= 180` minutos (`47,359` jugador-temporadas, `14,692` jugadores), descartando precisamente a suplentes jóvenes y prospectos en rotación donde suelen aparecer activos subvaluados. Por el contrario, incluir jugadores con pocos minutos usando tasas crudas por 90 minutos dispara valores extremos por varianza muestral (hasta `3.1579` goles más asistencias por 90 minutos en el tramo de `90` a `450` minutos).

Para retener la población desde `>= 180` minutos sin contaminar K-Means ni las regresiones, evaluamos el suavizado Empirical Bayes por posición `r_hat = (conteo + m * prior_pos) / ((minutos / 90) + m)`, ajustando `prior_pos` solo en las temporadas de entrenamiento `2017` a `2023` (`Attack = 0.4858`, `Midfield = 0.2315`, `Defender = 0.1064` en goles más asistencias por 90) y midiendo el error contra la temporada siguiente `t + 1` en los `2,378` casos reales de jugadores que pasaron de pocos minutos (`90` a `630`) a titulares (`>= 900`) al año siguiente (`06_minute_smoothing_sensitivity.csv` y `fig03_population_and_smoothing.png`):

| Fuerza del prior `m` (equivalentes de 90 min) | Máximo G+A/90 en `90` a `450` min | RMSE hacia temporada `t + 1` | Correlación de Pearson `r` con `t + 1` |
| --- | --- | --- | --- |
| `0.0` (tasa cruda) | `3.1579` | `0.3143` | `0.4251` |
| `2.0` (`180` min) | `1.6297` | `0.2165` | `0.5492` |
| `3.0` (`270` min) | `1.4130` | `0.1991` | `0.5818` |
| `5.0` (`450` min) | `1.1947` | `0.1809` | `0.6227` |
| `7.0` (`630` min) | `1.0721` | `0.1722` | `0.6455` |

Durante la revisión discutimos si convenía sustituir `RMSE` como función de pérdida principal, tanto en la calibración de `m` como en la regresión de valor de mercado. En tasas de conteo asimétricas y en precios de jugadores, el error cuadrático castiga con fuerza los valores altos inusuales: en `m` premia encoger cada vez más hacia el promedio posicional (incluso a costa de comprimir a juveniles sobresalientes), y en valuación puede desplazar el ajuste hacia traspasos inflados frente a alternativas menos sensibles a colas como `MAE` o pérdida de Huber. Sin embargo, el alcance académico comprometido en [docs/CONTEXT.md](CONTEXT.md) §4 exige entrenar regresión lineal múltiple y regresión polinomial mediante mínimos cuadrados ordinarios (que minimizan `MSE` y `RMSE`). Decidimos mantener el ajuste cuadrático sobre `log10(market_value_in_eur)` por consistencia con el temario del curso, fijar un valor intermedio `m = 5` (que reduce `42.4%` el `RMSE` interanual y conserva las variables crudas de volumen `minutes_played` y `starter_ratio`), y reportar `MAE` en escala logarítmica y `MdAPE` en euros junto a `RMSE` y `R^2` en la evaluación.

### H-06. Descarte de la tabla `game_events` tras auditar ruido y texto libre

Analizamos las `1,274,469` filas de `game_events` para decidir si aportaban variables que no estuvieran ya en `appearances` y `game_lineups` (`07b_game_events_breakdown.csv`). Más del `80%` de la tabla resultó redundante o contaminante para nuestro problema:

1. `Substitutions` concentra `631,339` filas (`49.54%`), incluye `93,157` descripciones vacías (`""`) y duplica la información de titularidad y minutos que ya entregan `game_lineups.type` y `appearances.minutes_played`.
2. `Cards` suma `381,753` filas (`29.95%`), cuyos conteos de amarillas y rojas ya están limpios y sin nulos en `appearances`, mientras que el motivo disciplinario viene mezclado en texto libre.
3. `Shootout` aporta `13,574` filas (`1.07%`) correspondientes a tandas de desempate en copas que reglamentariamente no cuentan como goles oficiales del jugador.
4. Dentro de `Goals` (`247,803` filas, `19.44%`), todas las filas tienen `description` no vacía, pero incluyen `6,729` autogoles (`Own-goal`) y abarcan `88,813` partidos desde 2006 frente a los `73,426` partidos cubiertos por `appearances` desde 2012.

La única señal adicional dentro de `Goals` era separar los `21,898` goles de penal (`8.84%` de los eventos de gol) para calcular goles sin penal por 90 minutos. Optamos por excluir `game_events` por completo (Opción 1) por tres razones prácticas: extraer penales obligaba a buscar subcadenas en inglés sobre `8,931` variantes de texto libre sin una columna booleana nativa; añadía la limpieza y pruebas de `1.27` millones de filas entrando a la semana 5 del calendario; y habría forzado al modo interactivo `POST /players/what-if` a pedirle al usuario el desglose de goles de penal. Asumimos como limitación documentada para la discusión del reporte final que los cobradores habituales de penales conservan ese volumen dentro de `goals`.

### H-07. Fuga temporal en columnas estáticas, anomalías de formato y viabilidad del cruce con `transfers`

La tabla `players` mezcla datos biográficos fijos con el estado del jugador en julio de 2026. Al cruzar `players` contra las `347,548` valuaciones históricas de `2017` a `2023`, medimos tres fuentes directas de fuga del futuro: `players.current_club_id` difiere del club real en la fecha de valuación en el `47.47%` de los casos; `players.highest_market_value_in_eur` supera el valor puntual en el `88.49%` (revelando si el jugador alcanzó después un pico mayor); y `players.contract_expiration_date` (cuando existe) cae en 2025 o después en el `71.84%` de las filas antiguas. Además, `clubs.total_market_value` está `100%` vacío (`796` de `796` nulos). Prohibimos todas esas columnas estáticas como predictores y establecimos una partición estrictamente cronológica: entrenamiento de `2017` a `2023`, validación en `2024` y prueba final en `2025` ([docs/ML_ARCHITECTURE.md](ML_ARCHITECTURE.md) §3.4).

Durante la primera corrida de `analysis/eda.py` apareció también un error real de formato que habría afectado a `clean`: `appearances`, `games`, `game_lineups`, `player_valuations` y `transfers` guardan fechas como `"YYYY-MM-DD"`, pero `players.date_of_birth` y `players.contract_expiration_date` incluyen sufijo de hora (`"YYYY-MM-DD HH:MM:SS"`). Parsear con formato exacto `%Y-%m-%d` convirtió todas las fechas de nacimiento a `NaT` y dejó vacía la muestra de edades hasta que normalizamos la lectura recortando los primeros 10 caracteres ISO. Documentamos esa regla en §3.5 junto con el parseo de decimales `"700000.000"` en `transfers`, la conversión de `25,698` guiones `"-"` en `game_lineups.number` a nulo, el descarte de `3` apariciones con `minutes_played <= 0`, el tope en `120` para `3` filas con `minutes_played > 120`, el reemplazo a nulo de `13` estaturas menores a `140` cm para imputarlas solo con la mediana posicional de `train` en `transform`, y la distinción entre `transfer_fee == 0` (`96,085` traspasos libres o préstamos) y nulo (`61,526` montos no revelados).

Por último, verificamos dos insumos necesarios para las semanas 5 y 6: la edad muestra una relación no lineal marcada con `log10(market_value_in_eur)` (`R^2` cuadrático `0.0763` frente a `0.0414` lineal, con pico cuadrático en `24.68` años y sesgo de selección en juveniles de 18 a 19 años que ya suman minutos de primera división, `fig04_age_valuation_nonlinearity.png`), y el cruce de `transfers` conserva `5,325` transferencias pagadas de jugadores de campo en las 14 ligas (`2017` a `2025`, con valuación previa y `>= 180` minutos en los 365 días estrictamente anteriores a `transfer_date`, incluidas `760` compras desde ligas *feeder* hacia las cinco grandes ligas; `08_transfers_join_audit.csv` y `fig06_transfer_fee_vs_valuation.png`). Incluso antes de entrenar nuestro modelo, el diferencial `log10(transfer_fee) - log10(market_value_in_eur)` sobre esas `5,325` operaciones se aleja significativamente de cero (`t = -15.554`, `p = 2.21e-53`; prueba de Wilcoxon `p = 3.45e-45`; razón media `fee / MV = 1.1481`, mediana `0.9133`, con `40.30%` de traspasos pagados por encima de su tasación previa).

## 4. Referencias internas

- [docs/CONTEXT.md](CONTEXT.md): propuesta base, estrategia KDD y calendario original.
- [docs/ARCHITECTURE.md](ARCHITECTURE.md): arquitectura de software y registro de decisiones ADR-001 a ADR-014.
- [docs/ML_ARCHITECTURE.md](ML_ARCHITECTURE.md): lista de decisiones de diseño de minería de datos (§3.1 a §3.18).
- [docs/WORK_PLAN.md](WORK_PLAN.md): comparativa entre calendario base y avance real, varianzas V-01 a V-03 y bitácora de decisiones.
