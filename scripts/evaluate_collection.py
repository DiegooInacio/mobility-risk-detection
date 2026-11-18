"""Compara perfis métricos nos mesmos mapas, preservando a referência original."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import sys

from mobility_risk.cli import main as analyze_image
from mobility_risk.metric import MetricConfig


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", type=Path, default=Path("experiments/coleta02.json"))
    parser.add_argument("--maps-dir", type=Path, default=Path("outputs/coleta02/baseline"))
    parser.add_argument("--output", type=Path, default=Path("outputs/coleta02/comparacao"))
    parser.add_argument("--profiles", type=Path,
                        help="JSON {nome: parâmetros de MetricConfig}; sem ajustes por imagem")
    args = parser.parse_args(argv)
    collection = json.loads(args.collection.read_text(encoding="utf-8"))
    profiles = {
        "referencia-2m": {},
        "alcance-2.5m": {"max_distance_m": 2.5},
        "alcance-3m": {"max_distance_m": 3.0},
    } if args.profiles is None else json.loads(args.profiles.read_text(encoding="utf-8"))
    if not isinstance(profiles, dict) or not profiles:
        parser.error("Forneça ao menos um perfil.")
    configs = {}
    for name, parameters in profiles.items():
        if not name or name in (".", "..") or Path(name).name != name or "\\" in name:
            parser.error("Nomes dos perfis devem ser nomes simples de pasta.")
        try:
            configs[name] = MetricConfig(**parameters)
        except (TypeError, ValueError) as exc:
            parser.error(f"Perfil {name}: {exc}")
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("O destino já contém arquivos. Use --output com uma pasta nova para preservar a comparação.")
    inputs = []
    for record in collection["images"]:
        image = Path(record["image"])
        depth = Path(record["depth_map"]) if "depth_map" in record else args.maps_dir / image.stem / "depth.npy"
        metadata = depth.with_suffix(".meta.json")
        if not image.is_file() or not depth.is_file() or not metadata.is_file():
            parser.error(f"Foto ou mapa com metadados ausente: {image}.")
        if json.loads(metadata.read_text(encoding="utf-8"))["depth_kind"] != "metric_m":
            parser.error(f"Mapa não métrico: {depth}.")
        inputs.append((record, image, depth, metadata))
    if not inputs or len({image.stem for _, image, _, _ in inputs}) != len(inputs):
        parser.error("A coleta deve conter imagens com nomes únicos e não pode estar vazia.")
    # Registra identidade das entradas e do código antes de executar comparações.
    args.output.mkdir(parents=True, exist_ok=True)
    sources = [Path("ai/mobility_risk") / name for name in
               ("analysis.py", "metric.py", "cli.py", "depth.py")]
    sources += [Path(__file__), Path("pyproject.toml")]
    snapshot = args.output / "source_snapshot"
    snapshot.mkdir()
    for index, source in enumerate(sources):
        (snapshot / f"{index}-{source.name}").write_bytes(source.read_bytes())
    versions = {}
    for package in ("numpy", "Pillow", "torch", "transformers"):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = None
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version, "package_versions": versions,
        "collection": collection,
        "profiles": {name: vars(config) for name, config in configs.items()},
        "source_sha256": {str(path): digest(path) for path in sources},
        "inputs": [{"image": str(image), "image_sha256": digest(image),
                    "depth": str(depth), "depth_sha256": digest(depth),
                    "metadata_sha256": digest(metadata)}
                   for _, image, depth, metadata in inputs],
        "note": "Comparação exploratória de sensibilidade, sem seleção automática de melhor configuração.",
    }
    (args.output / "run.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                          encoding="utf-8")
    rows = []
    for record, image, depth, _ in inputs:
        for name, config in configs.items():
            destination = args.output / name / image.stem
            command = [str(image), "--rule", "metric", "--depth-map", str(depth),
                       "--output", str(destination)]
            for key, value in vars(config).items():
                command += ["--" + key.replace("_", "-"), str(value)]
            analyze_image(command)
            report = json.loads((destination / "report.json").read_text(encoding="utf-8"))
            diagnostic = report["diagnostics"]
            rows.append({
                "image": str(image), "scene": record.get("scene", ""), "group": record.get("group", ""),
                "approximate_distance_m": record.get("approximate_distance_m"),
                "profile": name, **vars(config), "status": report["status"],
                "closeness_pass_fraction": diagnostic["closeness_pass_fraction"],
                "raw_candidate_area_fraction": diagnostic["raw_candidate_area_fraction"],
                "candidate_area_fraction": report["candidate_area_fraction"],
                "kept_component_count": diagnostic["kept_component_count"],
                "area_pass": report["decision"]["area_pass"],
                "width_pass": report["decision"]["width_pass"],
                "reason": diagnostic["reason"], "report": str(destination / "report.json"),
            })
    with (args.output / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Comparação registrada em {args.output / 'summary.csv'}")


if __name__ == "__main__":
    main()
