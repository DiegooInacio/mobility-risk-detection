"""Executa a regra métrica nas fotos da comparação anterior e reúne os resultados."""

import argparse
import csv
import json
from pathlib import Path

from mobility_risk.cli import main as analyze_image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images-dir", type=Path, default=Path("fotos"))
    parser.add_argument("--baseline-dir", type=Path, default=Path("outputs/diagnostico"))
    parser.add_argument("--output", type=Path, default=Path("outputs/metric"))
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--reuse-maps", action="store_true",
                        help="Reanalisa mapas métricos existentes; gera os que estiverem faltando")
    args = parser.parse_args()
    baselines = sorted(args.baseline_dir.glob("*/lateral-0.20/report.json"))
    if not baselines:
        parser.error("Nenhuma comparação anterior encontrada; execute scripts/compare_rules.py.")
    inputs = []
    for baseline in baselines:
        name = baseline.parent.parent.name
        photos = [p for p in args.images_dir.glob(f"{name}.*")
                  if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
        if len(photos) != 1:
            parser.error(f"Esperava exatamente uma foto para {name}.")
        inputs.append((name, photos[0]))
    rows = []
    for name, photo in inputs:
        destination = args.output / name
        command = [str(photo), "--rule", "metric", "--device", args.device,
                   "--output", str(destination)]
        if args.reuse_maps and (destination / "depth.npy").is_file():
            command += ["--depth-map", str(destination / "depth.npy")]
        analyze_image(command)
        paths = sorted((args.baseline_dir / name).glob("*/report.json"))
        paths.append(destination / "report.json")
        for path in paths:
            report = json.loads(path.read_text(encoding="utf-8"))
            config = report["config"]
            rows.append({
                "image": str(photo), "rule": report["rule"], "depth_kind": report["depth_kind"],
                "min_closeness": config.get("min_closeness", ""),
                "max_distance_m": config.get("max_distance_m", ""),
                "min_floor_gap_m": config.get("min_floor_gap_m", ""),
                "status": report["status"],
                "candidate_area_fraction": report["candidate_area_fraction"],
                "reason": report["diagnostics"]["reason"], "report": str(path),
            })
    with (args.output / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Comparação salva em: {args.output / 'summary.csv'}")


if __name__ == "__main__":
    main()
