"""Mide el rendimiento de un detector YOLO con fotos etiquetadas."""
import argparse
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from entrenar import BASE, validar_pares


def preparar_evaluacion(fotos, etiquetas, destino, nombres):
    pares = validar_pares(fotos, etiquetas, len(nombres))
    for foto, etiqueta, relativo in pares:
        imagen = destino / "images" / relativo
        anotacion = destino / "labels" / relativo.with_suffix(".txt")
        for origen, copia in ((foto, imagen), (etiqueta, anotacion)):
            copia.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origen, copia)
    data = destino / "data.yaml"
    # Ultralytics requiere las claves train y val, aunque aquí solo se evalúa.
    data.write_text(json.dumps({
        "path": destino.as_posix(),
        "train": "images",
        "val": "images",
        "names": nombres,
    }), encoding="utf-8")
    return data, len(pares)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelo", type=Path, required=True, help="Pesos locales .pt")
    origen = parser.add_mutually_exclusive_group(required=True)
    origen.add_argument("--data", type=Path, help="Archivo data.yaml de un dataset YOLO")
    origen.add_argument("--fotos", type=Path, help="Carpeta de fotos de evaluación")
    parser.add_argument("--etiquetas", type=Path, help="TXT YOLO para --fotos, por defecto junto a cada foto")
    parser.add_argument("--split", choices=("val", "test"), default="val")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=2)
    parser.add_argument("--device", help="cpu o índice de GPU, por ejemplo 0")
    parser.add_argument("--salida", type=Path, default=BASE / "evaluaciones")
    args = parser.parse_args()
    if not args.modelo.is_file() or (args.data and not args.data.is_file()):
        parser.error("Revisa las rutas de --modelo y --data.")
    if args.data and args.etiquetas:
        parser.error("--etiquetas requiere --fotos.")
    if args.fotos and args.split == "test":
        parser.error("--split test requiere --data. Con --fotos se evalúa la carpeta completa.")
    if min(args.imgsz, args.batch) < 1:
        parser.error("--imgsz y --batch deben ser positivos.")
    try:
        from ultralytics import YOLO
    except ModuleNotFoundError as error:
        parser.error(f"Falta {error.name}. Instala las dependencias con python -m pip install -r requirements.txt.")

    modelo = YOLO(str(args.modelo.resolve()))
    if modelo.task != "detect":
        parser.error("Usa un modelo YOLO de detección de cajas.")
    opciones = dict(split=args.split, imgsz=args.imgsz, batch=args.batch,
                    workers=0, project=str(args.salida.resolve()), name="evaluacion",
                    exist_ok=False, plots=True)
    if args.device is not None:
        opciones["device"] = args.device
    if args.fotos:
        fotos = args.fotos.resolve()
        etiquetas = (args.etiquetas or fotos).resolve()
        if not fotos.is_dir() or not etiquetas.is_dir():
            parser.error("Revisa las carpetas de fotos y etiquetas.")
        with TemporaryDirectory(prefix="visualshelf_eval_") as temporal:
            nombres = [modelo.names[i] for i in range(len(modelo.names))]
            try:
                data, cantidad = preparar_evaluacion(fotos, etiquetas, Path(temporal), nombres)
            except ValueError as error:
                parser.error(str(error))
            print(f"Fotos evaluadas: {cantidad}")
            metricas = modelo.val(data=str(data), **opciones)
    else:
        metricas = modelo.val(data=str(args.data.resolve()), **opciones)

    cajas = metricas.box
    print("\nResumen de detección")
    print(f"Precisión: {cajas.mp:.1%} | Exhaustividad: {cajas.mr:.1%}")
    print(f"mAP50: {cajas.map50:.1%} | mAP50–95: {cajas.map:.1%}")
    print(f"Directorio de salida de los gráficos: {args.salida.resolve()}")


if __name__ == "__main__":
    main()
