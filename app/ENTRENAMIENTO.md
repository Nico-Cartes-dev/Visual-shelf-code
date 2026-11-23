# Entrenar con fotos de una carpeta

Ejecuta los comandos desde esta carpeta (`app`). Se ajusta el `best.pt`
existente; el original no se reemplaza. No es necesario subir las fotos a Roboflow.

## 1. Preparar fotos y etiquetas

Pon las fotos y sus etiquetas juntas, por ejemplo `C:\dataset\fotos\foto01.jpg`
y `C:\dataset\fotos\foto01.txt`. Tambien puedes separar los TXT con
`--etiquetas "C:\dataset\etiquetas"`, manteniendo los mismos nombres y subcarpetas.

Cada TXT contiene una linea por producto:

```text
0 0.50 0.50 0.20 0.30
```

Formato: `clase centro_x centro_y ancho alto`, con coordenadas normalizadas
entre 0 y 1. Usa las mismas clases y el mismo orden que el modelo original;
el script los obtiene de `best.pt` y los muestra antes de entrenar.
Un TXT vacio significa una foto sin objetos de las clases objetivo; usalo
solo cuando realmente no aparezcan. Anota todos los productos visibles.
Puedes etiquetar manualmente con herramientas como CVAT o Label Studio y
exportar en formato YOLO de deteccion. Las predicciones del modelo pueden
ayudar como borrador, pero deben corregirse antes de usarlas como etiquetas.

## 2. Instalar y entrenar

```powershell
python -m pip install -r requirements.txt
python entrenar.py --fotos "C:\dataset\fotos"
```

Opciones para GPU NVIDIA con PyTorch compatible con CUDA instalado:

```powershell
python entrenar.py --fotos "C:\dataset\fotos" --device 0 --epochs 100 --imgsz 640 --batch 2
```

Para CPU usa `--device cpu`; sera mas lento. Si falta memoria GPU, baja
`--batch` a 1. Puedes probar `--imgsz 1024` para productos pequenos si tu
hardware lo permite. La instalacion de requirements por si sola no garantiza CUDA.

El script copia las fotos y etiquetas a una carpeta nueva, separa 80 % para
entrenar y 20 % para validar, y genera `data.yaml`. No modifica los originales.
Necesita al menos dos fotos, pero ese minimo no basta para evaluar calidad.
Evita fotos casi identicas de una misma gondola: la division es aleatoria
por foto y no agrupa por tienda o sesion. Para una evaluacion fiable, reserva
ademas fotos independientes de otras sesiones que no entren en esta carpeta.
Conviene mezclar ejemplos anteriores con los nuevos para reducir el olvido.

Durante el entrenamiento, YOLO aplica giros aleatorios de hasta ±8° y voltea
horizontalmente las imágenes con un 50 % de probabilidad. YOLO ajusta las cajas
junto con cada imagen. Las variantes se generan al cargar cada lote, después
de separar la validación, y las fotos originales se conservan.

Usa `--grados 5 --volteo 0.25` para reducir esos aumentos, o
`--grados 0 --volteo 0` para desactivar ambos.

## 3. Probar el resultado en la app

El nuevo modelo queda en `entrenamientos/ajuste_.../modelo/weights/best.pt`.
Ultralytics muestra tambien metricas y graficos dentro de `modelo`.

```powershell
python app.py --modelo "entrenamientos\ajuste_...\modelo\weights\best.pt"
```

Reemplaza `ajuste_...` por la carpeta real y compara con fotos independientes
antes de adoptar el modelo nuevo. Este ajuste inicia un entrenamiento nuevo
desde los pesos existentes; no reanuda el estado de una ejecucion interrumpida.

## 4. Entrenar con un dataset externo

[SKU-110K](https://github.com/eg4000/SKU110K_CVPR19#dataset) tiene fotos de
góndolas densas con cajas de una sola clase. Sus autores lo restringen a uso
académico y no comercial. Ultralytics descarga y convierte el dataset en la
primera ejecución. La descarga es de unos 13,6 GB y se necesita espacio
adicional para extraerla. Se usan las particiones oficiales.

```powershell
python entrenar.py --data SKU-110K.yaml --device 0 --batch 2
```

Para otro dataset, exporta en formato YOLO de detección y descomprime el
archivo. Usa un dataset con una clase de producto y revisa que las anotaciones
cubran los formatos que quieres contar. Por ejemplo, [DBAI Retail Shelf en
Roboflow](https://universe.roboflow.com/dbai/retail-shelf-l96n8-pefrn) registra
una versión de 44 imágenes, clase Product y licencia publicada CC BY 4.0.

```powershell
python entrenar.py --data "C:\dataset\retail-shelf\data.yaml" --device 0 --batch 2
```

Con `--data` se respetan las particiones del YAML. Para entrenar con varios
conjuntos a la vez, usa un YAML con una lista de rutas en `train` y otra en
`val`, con la clase `0` para producto en todas las etiquetas. Reserva una
sesión local anotada a mano para comparar el modelo nuevo con el anterior.
