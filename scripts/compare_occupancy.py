"""Compara ocupação 2D com resultados anteriores, sem ler mapas de profundidade."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path

from mobility_risk.cli import main as analyze_image
from mobility_risk.occupancy import OccupancyConfig


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", type=Path, default=Path("experiments/coleta-comparacao-largura.json"))
    parser.add_argument("--instances-dir", type=Path, default=Path("outputs/comparacao-objetos/objects-2m"))
    parser.add_argument("--reference", type=Path, default=Path("outputs/comparacao-objetos/summary.csv"))
    parser.add_argument("--output", type=Path, default=Path("outputs/comparacao-ocupacao"))
    args = parser.parse_args(argv)
    collection = json.loads(args.collection.read_text(encoding="utf-8"))
    records = collection["images"]
    if not records or len({Path(r["image"]).stem for r in records}) != len(records):
        parser.error("A coleta não pode ser vazia ou conter nomes repetidos.")
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Destino não vazio. Escolha uma pasta nova com --output.")
    with args.reference.open(encoding="utf-8", newline="") as handle:
        references = list(csv.DictReader(handle))
    wanted = {Path(record["image"]).resolve() for record in records}
    references = [row for row in references if Path(row["image"]).resolve() in wanted]
    expected = {f"{rule}-{distance}m" for rule in ("metric", "objects", "hybrid") for distance in (2, 3)}
    for record in records:
        image = Path(record["image"])
        cache = args.instances_dir / image.stem / "instances.npz"
        if not image.is_file() or not cache.is_file() or not cache.with_suffix(".meta.json").is_file():
            parser.error(f"Foto ou cache de segmentação ausente: {image}.")
        profiles = [row["profile"] for row in references if Path(row["image"]).resolve() == image.resolve()]
        if set(profiles) != expected or len(profiles) != len(expected):
            parser.error(f"Referência incompleta ou duplicada para {image}.")
    args.output.mkdir(parents=True, exist_ok=True)
    sources = [Path("ai/mobility_risk") / name for name in ("analysis.py", "metric.py", "objects.py", "occupancy.py", "cli.py", "depth.py")]
    sources += [Path(__file__), Path("pyproject.toml")]
    snapshot = args.output / "source_snapshot"
    snapshot.mkdir()
    for index, path in enumerate(sources):
        (snapshot / f"{index}-{path.name}").write_bytes(path.read_bytes())
    versions = {}
    for package in ("numpy", "Pillow", "ultralytics"):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = None
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(), "collection": collection,
        "config": vars(OccupancyConfig()), "package_versions": versions,
        "reference": str(args.reference), "reference_sha256": digest(args.reference),
        "source_sha256": {str(path): digest(path) for path in sources},
        "inputs": [{"image": r["image"], "image_sha256": digest(Path(r["image"])),
                    "instances_sha256": digest(args.instances_dir / Path(r["image"]).stem / "instances.npz"),
                    "metadata_sha256": digest(args.instances_dir / Path(r["image"]).stem / "instances.meta.json")}
                   for r in records],
        "note": "Somente imagem e máscaras. Referências anteriores são resultados lidos de CSV, não novas inferências.",
    }
    (args.output / "run.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    rows = []
    for record in records:
        image = Path(record["image"])
        destination = args.output / "occupancy" / image.stem
        analyze_image([str(image), "--rule", "occupancy", "--instances",
                       str(args.instances_dir / image.stem / "instances.npz"), "--output", str(destination)])
        report = json.loads((destination / "report.json").read_text(encoding="utf-8"))
        matched = [row for row in references if Path(row["image"]).resolve() == image.resolve()]
        for reference in matched:
            rows.append({
                "image": str(image), "group": record.get("group", ""), "profile": reference["profile"],
                "result_kind": "previous_depth_based", "status": reference["status"],
                "region_fraction": reference["candidate_area_fraction"],
                "fraction_meaning": "Máscara da regra anterior; não equivale à ocupação ou eficácia.",
                "report": reference["report"],
            })
        rows.append({
            "image": str(image), "group": record.get("group", ""), "profile": "occupancy",
            "result_kind": "spatial_occupancy_only", "status": report["status"],
            "region_fraction": report["occupancy_area_fraction"],
            "fraction_meaning": "União das máscaras aceitas dentro da ROI; sem distância.",
            "report": str(destination / "report.json"),
        })
    with (args.output / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Comparação salva em {args.output / 'summary.csv'}")


if __name__ == "__main__":
    main()
