"""Compara regras nos mapas salvos; não carrega o modelo nem atribui rótulos."""

import argparse
import csv
import json
from pathlib import Path

from mobility_risk.cli import main as analyze_image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images-dir", type=Path, default=Path("fotos"))
    parser.add_argument("--maps-dir", type=Path, default=Path("outputs/comparacao"))
    parser.add_argument("--output", type=Path, default=Path("outputs/diagnostico"))
    args = parser.parse_args()
    maps = sorted(args.maps_dir.glob("*/original/depth.npy"))
    if not maps:
        parser.error("Nenhum mapa encontrado em --maps-dir/*/original/depth.npy.")
    inputs = []
    for depth in maps:
        name = depth.parent.parent.name
        photos = [p for p in args.images_dir.glob(f"{name}.*")
                  if p.suffix.lower() in (".jpeg", ".jpg", ".png", ".webp")]
        if len(photos) != 1:
            parser.error(f"Esperava exatamente uma imagem para {name}; encontradas: {len(photos)}.")
        inputs.append((name, photos[0], depth))
    rows = []
    for name, photo, depth in inputs:
        for rule in ("lateral", "floor"):
            for closeness in (0.60, 0.20):
                destination = args.output / name / f"{rule}-{closeness:.2f}"
                analyze_image([str(photo), "--depth-map", str(depth), "--rule", rule,
                               "--min-closeness", str(closeness), "--output", str(destination)])
                report = json.loads((destination / "report.json").read_text(encoding="utf-8"))
                diagnostic = report["diagnostics"]
                rows.append({
                    "image": str(photo), "rule": rule, "min_closeness": closeness,
                    "status": report["status"],
                    "closeness_pass_fraction": diagnostic["closeness_pass_fraction"],
                    "contrast_pass_fraction": diagnostic["contrast_pass_fraction"],
                    "candidate_area_fraction": report["candidate_area_fraction"],
                    "reason": diagnostic["reason"], "report": str(destination / "report.json"),
                })
    with (args.output / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Comparação salva em: {args.output / 'summary.csv'}")


if __name__ == "__main__":
    main()
