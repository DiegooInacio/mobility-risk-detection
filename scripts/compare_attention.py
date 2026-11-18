"""Compara máscaras, caixas e margens 2D usando as mesmas instâncias salvas."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path

from mobility_risk.attention import AttentionConfig
from mobility_risk.cli import main as analyze_image


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", type=Path, default=Path("experiments/coleta-comparacao-largura.json"))
    parser.add_argument("--instances-dir", type=Path, default=Path("outputs/comparacao-objetos/objects-2m"))
    parser.add_argument("--margins", type=float, nargs="+", default=[0.0, 0.15, 0.30])
    parser.add_argument("--output", type=Path, default=Path("outputs/comparacao-atencao"))
    args = parser.parse_args(argv)
    for margin in args.margins:
        try:
            AttentionConfig(margin_fraction=margin)
        except ValueError as exc:
            parser.error(str(exc))
    if len(set(args.margins)) != len(args.margins):
        parser.error("As margens devem ser distintas.")
    collection = json.loads(args.collection.read_text(encoding="utf-8"))
    records = collection["images"]
    if not records or len({Path(r["image"]).stem for r in records}) != len(records):
        parser.error("A coleta não pode ser vazia ou conter nomes repetidos.")
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Destino não vazio. Escolha outra pasta com --output.")
    for record in records:
        image = Path(record["image"])
        cache = args.instances_dir / image.stem / "instances.npz"
        if not image.is_file() or not cache.is_file() or not cache.with_suffix(".meta.json").is_file():
            parser.error(f"Foto ou cache de segmentação ausente: {image}.")
    args.output.mkdir(parents=True, exist_ok=True)
    sources = [Path("ai/mobility_risk") / name for name in
               ("analysis.py", "attention.py", "occupancy.py", "objects.py", "cli.py", "depth.py", "metric.py")]
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
        "margins": args.margins, "attention_defaults": vars(AttentionConfig()),
        "package_versions": versions,
        "source_sha256": {str(path): digest(path) for path in sources},
        "inputs": [{"image": r["image"], "image_sha256": digest(Path(r["image"])),
                    "instances_sha256": digest(args.instances_dir / Path(r["image"]).stem / "instances.npz"),
                    "metadata_sha256": digest(args.instances_dir / Path(r["image"]).stem / "instances.meta.json")}
                   for r in records],
        "note": "Caixas e margens na imagem, sem profundidade ou inferência de aproximação física.",
    }
    (args.output / "run.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    rows = []
    for record in records:
        image = Path(record["image"])
        cache = args.instances_dir / image.stem / "instances.npz"
        profiles = [("occupancy", "occupancy", None)] + [
            ("attention", f"attention-{margin:g}", margin) for margin in args.margins]
        for rule, profile, margin in profiles:
            destination = args.output / profile / image.stem
            command = [str(image), "--rule", rule, "--instances", str(cache), "--output", str(destination)]
            if margin is not None:
                command += ["--attention-margin", str(margin)]
            analyze_image(command)
            report = json.loads((destination / "report.json").read_text(encoding="utf-8"))
            rows.append({
                "image": str(image), "group": record.get("group", ""), "profile": profile,
                "margin_fraction": margin, "status": report["status"],
                "attention_area_fraction": report.get("attention_area_fraction", ""),
                "object_occupancy_area_fraction": report.get("object_occupancy_area_fraction", report.get("occupancy_area_fraction")),
                "activated_instance_count": sum(obj["alert"] for obj in report["objects"]),
                "activated_classes": ";".join(sorted({obj["class_name"] for obj in report["objects"] if obj["alert"]})),
                "reason": report["diagnostics"]["reason"], "report": str(destination / "report.json"),
            })
    with (args.output / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Comparação salva em {args.output / 'summary.csv'}")


if __name__ == "__main__":
    main()
