# Arquitectura de VisualShelf

VisualShelf estima la ocupación visible de una góndola a partir de una fotografía. La aplicación combina un detector YOLO con reglas geométricas y de calidad de imagen. El resultado incluye la estimación de stock, los productos considerados, las filas, los huecos, el estado y una imagen anotada.

## Componentes y flujo de una fotografía

1. La interfaz en [app/static](../app/static/) inicia sesión, permite seleccionar tienda y jornada, y envía una solicitud por foto con un identificador, la imagen y los parámetros de análisis.
2. El servidor de [app/app.py](../app/app.py) verifica el token y la membresía en la tienda, valida la solicitud y crea un registro pendiente. Corrige la orientación EXIF, conserva la fecha de captura cuando está disponible y reduce el lado mayor a 4000 píxeles si hace falta. Convierte la imagen a BGR para el motor.
3. El motor de [app/motor.py](../app/motor.py) recibe la imagen y devuelve las métricas y una imagen anotada. Los pesos se cargan al arrancar. Un candado protege el detector compartido y los parámetros por solicitud. Si otra foto ocupa el detector, la API responde con HTTP 429.
4. El servidor genera JPEG de la foto de entrada procesada y de la vista anotada. Mediante [app/central.py](../app/central.py), guarda los archivos en el depósito privado de Storage y registra sus rutas, el resultado y la huella SHA-256 de los pesos en PostgreSQL.
5. La interfaz consulta los análisis completos y solicita las imágenes a través de la API autenticada. Ante un fallo durante el análisis o la escritura, el servidor intenta borrar los archivos que alcanzó a guardar y marcar el registro como erróneo.

## Detección y estimación

### Cajas de producto y región de la góndola

`detectar_filtrada()` ejecuta YOLO con el umbral de confianza configurado. Por defecto comienza con la imagen completa. Si la altura mediana de las cajas es inferior al 6 % de la altura de la foto, prueba mosaicos solapados y adopta ese resultado cuando aporta al menos un 15 % más de detecciones. En el análisis por mosaicos, el motor traslada las cajas a las coordenadas de la foto y usa NMS para suprimir duplicados. NMS conserva primero la caja de mayor confianza y suprime las cajas cuyo IoU con ella supera el umbral de fusión.

La región de la góndola se estima expandiendo las cajas y aplicando cierre morfológico. El motor conserva las regiones conectadas con suficientes productos. Esta configuración usa solo el detector de cajas.

### Repisas, filas y huecos

`analizar_cajas()` busca frentes de repisa con Canny y Hough probabilística y comprueba que sean coherentes con las bases de los productos detectados. Asigna las cajas a las repisas cuando hay evidencia suficiente y usa RANSAC sobre las bases de las cajas para ajustar las filas restantes. Con pocas detecciones, puede estimar ocupación muestreando posiciones a lo largo de repisas visibles si estas tienen suficiente respaldo geométrico.

Dentro de cada fila, el motor ordena las cajas por posición horizontal. Una separación que supera `k_hueco` veces el ancho local de producto se divide en tramos según el paso entre productos. Los tramos con textura similar a la de un producto o con reflejos intensos se marcan como dudosos. Los demás aportan unidades faltantes estimadas. También puede inferir repisas vacías entre filas mediante líneas visibles o saltos en el espaciado vertical, y comprueba la textura de la franja antes de contabilizarlas. La configuración incluida desactiva el conteo de huecos en los extremos de cada fila en este cálculo.

### Stock y estado

El cálculo principal es **stock (%) = 100 × N / (N + U)**, donde **N** es el número de productos incorporados a la estimación y **U** las unidades faltantes estimadas. Por ejemplo, 24 productos y 6 unidades faltantes dan un 80 %. El conteo de detecciones de YOLO, el número de tramos marcados como huecos y las unidades faltantes representan magnitudes diferentes.

`calidad_img()` comprueba nitidez mediante la varianza del Laplaciano, brillo medio y zonas saturadas. `decidir()` aplica estas reglas en orden:

| Condición | Estado |
| --- | --- |
| La geometría o las detecciones no permiten estimar stock | `REVISION_MANUAL`, con `stock_pct` nulo en la API |
| El stock medible es estrictamente inferior al umbral | `ALERTA_REPONER`, aun si hay avisos de calidad |
| El stock alcanza el umbral y existen avisos de calidad o detección | `REVISION_MANUAL` |
| El stock alcanza el umbral y no hay avisos | `OK` |

El [archivo de parámetros](../app/parametros_v4.json) fija una confianza inicial de 0,35, resolución de inferencia de 1024 px y umbral de stock del 30 %. La interfaz permite ajustar la confianza y el umbral por solicitud. El resultado depende de la cobertura de la foto, la perspectiva, la iluminación y la capacidad del detector para identificar productos pequeños u ocluidos.

## API y persistencia

| Método y ruta | Función |
| --- | --- |
| `GET /api/auth-config` | Entrega la configuración pública necesaria para iniciar sesión. |
| `GET /api/config` | Devuelve usuario, tiendas asignadas y valores iniciales del análisis. |
| `POST /api/analizar` | Analiza una foto. Si su identificador ya corresponde a un análisis completo accesible, devuelve ese resultado. |
| `GET /api/analisis` | Lista hasta 50 registros completos por página. Admite filtros de tienda, jornada o alertas. |
| `GET /api/analisis/{id}/original` y `GET /api/analisis/{id}/anotada` | Recuperan la foto de entrada procesada y la anotación, respectivamente. |
| `DELETE /api/analisis/{id}` | Elimina un análisis si lo solicita su autor o un administrador de la tienda. |
| `GET /api/resumen` | Consulta el resumen de los análisis visibles para el usuario. |
| `POST /api/importar` | Importa hasta 300 registros históricos por solicitud, sin imágenes. |

Las rutas protegidas usan un token Bearer del usuario. El esquema define `perfiles`, `tiendas`, la relación `usuarios_tiendas`, `gondolas` y `analisis`. Las políticas de seguridad a nivel de fila aplican el aislamiento por tienda a los registros y a las imágenes del depósito privado. [Esquema](../app/supabase/schema.sql) · [Guía de operación](../app/CENTRALIZACION.md)

## Entrenamiento y evaluación

El entrenamiento ajusta los pesos a partir de cajas etiquetadas en formato YOLO. Con fotos locales, el script prepara una división reproducible de entrenamiento y validación. Los pesos generados quedan en una carpeta nueva. [Guía de entrenamiento](../app/ENTRENAMIENTO.md)

Para medir la detección sobre un conjunto independiente con etiquetas YOLO, ejecuta desde la raíz con las dependencias instaladas:

```powershell
python evaluar.py --modelo app\best.pt --fotos "C:\dataset\evaluacion"
```

El script informa precisión, exhaustividad, mAP50 y mAP50–95, y guarda gráficos en `evaluaciones/`. Estas métricas evalúan las cajas. Para evaluar el porcentaje de stock, compara la salida de la aplicación con conteos de ocupación de referencia sobre fotos independientes. [Código de evaluación](../evaluar.py)
