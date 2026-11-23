# VisualShelf

VisualShelf analiza fotografías de góndolas para detectar productos, estimar el stock y señalar posibles reposiciones o revisiones manuales. La aplicación web usa un detector YOLO y guarda el historial compartido, las tiendas y las fotografías en Supabase.

## Requisitos

- Windows y Python 3.11.
- Acceso a Internet para la autenticación y los datos en Supabase.
- Los pesos del modelo `app/best.pt` (incluidos en el proyecto).

La aplicación funciona en CPU; una GPU compatible puede acelerar el análisis, pero no es necesaria para iniciarla.

## Inicio rápido en Windows

Abre PowerShell en la raíz del repositorio y ejecuta:

```powershell
cd app
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:Path = "$(Resolve-Path .\.venv\Scripts);$env:Path"
.\iniciar.ps1 --host 127.0.0.1
```

Estos comandos usan el entorno virtual sin ejecutar su script de activación. Si tienes varias versiones de Python instaladas, usa `py -3.11 -m venv .venv` para crearlo.

Cuando aparezca el mensaje de servidor iniciado, visita [http://127.0.0.1:7860](http://127.0.0.1:7860). Detén el servidor con `Ctrl+C`.

El script `app/iniciar.ps1` ya configura `SUPABASE_URL` y `SUPABASE_PUBLISHABLE_KEY` para la base de datos del proyecto. Para el uso local basta con iniciar la aplicación mediante ese script; no necesitas crear un archivo `.env` ni copiar las claves manualmente.

También se puede iniciar directamente desde `app`:

```powershell
python app.py
```

Opciones disponibles: `--modelo`, `--parametros`, `--puerto` y `--host`. Por ejemplo:

```powershell
python app.py --modelo best.pt --parametros parametros_v4.json --puerto 7860
```

Si inicias con `python app.py` en vez de `iniciar.ps1`, primero define `SUPABASE_URL` y `SUPABASE_PUBLISHABLE_KEY` en el entorno. Para Docker u otro host también debes definirlas allí; `.env.example` es solo una referencia y no se carga automáticamente. La clave configurada en `iniciar.ps1` es publicable; no uses una clave `service_role` en la aplicación.

## Cómo funciona

1. La persona inicia sesión. Supabase Auth valida la sesión y las políticas de acceso limitan cada cuenta a las tiendas asignadas.
2. La interfaz permite elegir tienda y jornada, ajustar los parámetros disponibles y cargar fotografías.
3. El servidor recibe cada imagen, corrige su orientación, limita su tamaño y la procesa con YOLO. El motor detecta productos y estima filas, huecos y porcentaje de stock. La evaluación produce estados como `OK`, `ALERTA_REPONER` o `REVISION_MANUAL`.
4. El resultado y las imágenes original y anotada se guardan en Supabase. Las fotografías se descargan mediante solicitudes autenticadas.
5. El historial compartido permite consultar análisis, filtrar alertas, revisar imágenes y exportar los registros cargados a CSV. También incluye resumen e importación del historial local.

El procesamiento usa un modelo compartido y ejecuta una solicitud de inferencia a la vez por instancia. Si está ocupado, la aplicación solicita reintentar la foto. El inicio rápido limita la escucha al equipo local. Sin `--host` ni la variable `HOST`, el servidor escucha en `0.0.0.0`.

## Algoritmos implementados

- **Detección de productos.** YOLO predice cajas y puntuaciones de confianza. El motor puede repetir la detección por mosaicos solapados y fusionar cajas duplicadas con supresión no máxima (NMS) basada en la intersección sobre unión (IoU).
- **Identificación de repisas y filas.** OpenCV busca líneas de repisa con Canny y la transformada de Hough. El motor usa RANSAC sobre las bases de las cajas para estimar filas que no puede asignar a una repisa.
- **Estimación de ocupación visible.** El motor compara los espacios entre cajas con el ancho de los productos cercanos. Usa textura y reflejos para descartar espacios ambiguos y estima cuántas unidades cabrían en los huecos medibles.
- **Decisión.** El motor compara el stock estimado con el umbral de reposición y considera los avisos de detección y calidad. El porcentaje representa la ocupación estimada en la foto. [Documentación técnica](docs/ARQUITECTURA.md)

## Estructura del proyecto

| Ruta | Propósito |
|---|---|
| `app/app.py` | Servidor HTTP, API, autenticación y flujo de análisis. |
| `app/central.py` | Acceso a Supabase Auth, PostgreSQL y Storage con la sesión del usuario. |
| `app/motor.py` | Detección YOLO y cálculo de stock y huecos. |
| `app/best.pt` | Pesos del modelo usados por defecto. |
| `app/parametros_v4.json` | Parámetros del detector y del análisis. |
| `app/static/` | Interfaz web, estilos y llamadas a la API. |
| `app/supabase/schema.sql` | Esquema y políticas para inicializar un proyecto Supabase nuevo. |
| `app/iniciar.ps1` | Arranque local en Windows. |
| `app/Dockerfile` | Imagen Docker de la aplicación. |
| `app/entrenar.py` | Entrenamiento o ajuste del modelo con imágenes etiquetadas. |
| `entrenar.py` y `evaluar.py` | Herramientas de la raíz para ajustar y evaluar un detector con etiquetas YOLO. |
| `docs/ARQUITECTURA.md` | Flujo de datos, algoritmos, API y persistencia. |
| `app/ENTRENAMIENTO.md` | Preparación de datos y opciones de entrenamiento y evaluación. |
| `app/CENTRALIZACION.md` | Configuración de usuarios, tiendas, permisos, operación y publicación. |

Las fotos etiquetadas se proporcionan por separado. La aplicación web y sus pesos de inicio están en `app/`.

## Usuarios y Supabase

La aplicación no incluye registro público ni administración de usuarios. Las cuentas se invitan desde Supabase Dashboard y se les asignan tiendas y roles (`admin` u `operador`) allí. Para poner en marcha una instalación Supabase nueva, revisa primero `app/CENTRALIZACION.md` y el esquema `app/supabase/schema.sql`; ese esquema está pensado para un proyecto vacío.

## Entrenamiento del modelo

Desde PowerShell, dentro de `app`, instala los requisitos y sigue las instrucciones de `ENTRENAMIENTO.md`. Ejemplo:

```powershell
python entrenar.py --fotos "C:\dataset\fotos"
```

Las imágenes deben tener etiquetas YOLO compatibles con las clases del modelo. El entrenamiento crea una nueva carpeta bajo `app/entrenamientos/` y no sustituye `app/best.pt`. Para probar un modelo nuevo en la aplicación:

```powershell
python app.py --modelo "entrenamientos\ajuste_xxxxx\modelo\weights\best.pt"
```

## Documentación adicional

- [Documentación técnica](docs/ARQUITECTURA.md)
- [Configuración centralizada y publicación](app/CENTRALIZACION.md)
- [Entrenamiento y evaluación](app/ENTRENAMIENTO.md)
- [README de la aplicación](app/README.md)
