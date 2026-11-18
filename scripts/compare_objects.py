"""Compara geometria, instâncias e união híbrida nos mesmos mapas métricos."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path

from mobility_risk.cli import main as analyze_image


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", type=Path, default=Path("experiments/coleta-comparacao-largura.json"))
    parser.add_argument("--output", type=Path, default=Path("outputs/comparacao-objetos"))
    parser.add_argument("--segment-model", type=Path, default=Path("outputs/models/yolo11n-seg.pt"))
    parser.add_argument("--instances-dir", type=Path,
                        help="Pasta contendo <nome>/instances.npz; gera as instâncias faltantes")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    args = parser.parse_args(argv)
    collection = json.loads(args.collection.read_text(encoding="utf-8"))
    records = collection["images"]
    if not records or len({Path(r["image"]).stem for r in records}) != len(records):
        parser.error("A coleta não pode estar vazia ou conter nomes repetidos.")
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Destino não vazio. Escolha outra pasta com --output.")
    for record in records:
        image, depth = Path(record["image"]), Path(record["depth_map"])
        if not image.is_file() or not depth.is_file() or not depth.with_suffix(".meta.json").is_file():
            parser.error(f"Foto ou mapa com metadados ausente: {image}.")
        if json.loads(depth.with_suffix(".meta.json").read_text())["depth_kind"] != "metric_m":
            parser.error(f"Mapa não métrico: {depth}.")
    args.output.mkdir(parents=True, exist_ok=True)
    sources = [Path("ai/mobility_risk") / name for name in
               ("analysis.py", "metric.py", "objects.py", "cli.py", "depth.py")]
    sources += [Path(__file__), Path("pyproject.toml")]
    snapshot = args.output / "source_snapshot"
    snapshot.mkdir()
    for index, source in enumerate(sources):
        (snapshot / f"{index}-{source.name}").write_bytes(source.read_bytes())
    versions = {}
    for package in ("numpy", "Pillow", "torch", "transformers", "ultralytics", "torchvision"):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = None
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(), "collection": collection,
        "package_versions": versions, "source_sha256": {str(p): digest(p) for p in sources},
        "inputs": [{"image": r["image"], "image_sha256": digest(Path(r["image"])),
                    "depth_map": r["depth_map"], "depth_sha256": digest(Path(r["depth_map"]))}
                   for r in records],
        "profiles": [{"rule": rule, "max_distance_m": distance}
                     for distance in (2.0, 3.0) for rule in ("metric", "objects", "hybrid")],
        "note": "Comparação exploratória. Ramo objects cobre apenas classes detectadas; hybrid preserva alertas geométricos.",
    }
    (args.output / "run.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                          encoding="utf-8")
    rows = []
    for record in records:
        image, depth = Path(record["image"]), Path(record["depth_map"])
        instances_path = args.instances_dir / image.stem / "instances.npz" if args.instances_dir else None
        if instances_path and not instances_path.is_file():
            instances_path = None
        for distance in (2.0, 3.0):
            for rule in ("metric", "objects", "hybrid"):
                profile = f"{rule}-{distance:.0f}m"
                destination = args.output / profile / image.stem
                command = [str(image), "--depth-map", str(depth), "--rule", rule,
                           "--max-distance-m", str(distance), "--device", args.device,
                           "--output", str(destination)]
                if rule != "metric":
                    command += ["--segment-model", str(args.segment_model)]
                    if instances_path:
                        command += ["--instances", str(instances_path)]
                analyze_image(command)
                if rule == "objects" and instances_path is None:
                    instances_path = destination / "instances.npz"
                report = json.loads((destination / "report.json").read_text(encoding="utf-8"))
                objects = report.get("objects", [])
                rows.append({
                    "image": str(image), "group": record.get("group", ""), "profile": profile,
                    "approximate_distance_m": record.get("approximate_distance_m"),
                    "max_distance_m": distance, "status": report["status"],
                    "candidate_area_fraction": report["candidate_area_fraction"],
                    "detected_instance_count": len(objects) if rule != "metric" else "",
                    "alert_instance_count": sum(item["alert"] for item in objects) if rule != "metric" else "",
                    "detected_classes": ";".join(sorted({item["class_name"] for item in objects})),
                    "alert_classes": ";".join(sorted({item["class_name"] for item in objects if item["alert"]})),
                    "geometry_status": report["branches"]["metric"]["status"] if rule == "hybrid" else "",
                    "report": str(destination / "report.json"),
                })
    with (args.output / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Comparação salva em {args.output / 'summary.csv'}")


if __name__ == "__main__":
    main()
