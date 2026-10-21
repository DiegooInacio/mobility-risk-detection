import argparse
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from .analysis import Config, analyze
from .depth import MODEL_ID, estimate


def main(argv=None):
    parser = argparse.ArgumentParser(description="POC de análise experimental de obstáculo frontal.")
    parser.add_argument("image", type=Path, help="Foto a analisar")
    parser.add_argument("--output", type=Path, default=Path("outputs/latest"))
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--depth-map", type=Path,
                        help="Reutiliza .npy de profundidade inversa relativa, sem carregar modelo")
    parser.add_argument("--min-closeness", type=float, default=0.60)
    parser.add_argument("--min-contrast", type=float, default=0.15)
    parser.add_argument("--min-area-fraction", type=float, default=0.05)
    args = parser.parse_args(argv)
    try:
        config = Config(min_closeness=args.min_closeness, min_contrast=args.min_contrast,
                        min_area_fraction=args.min_area_fraction)
        with Image.open(args.image) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
        start = perf_counter()
        if args.depth_map:
            depth = np.load(args.depth_map, allow_pickle=False)
            device = "precomputed"
        else:
            depth, device = estimate(image, args.device)
        depth_seconds = perf_counter() - start
        if depth.shape != (image.height, image.width):
            raise ValueError("O mapa deve ter as dimensões da foto após correção da orientação EXIF.")
        start = perf_counter()
        report, normalized, mask = analyze(depth, config)
        analysis_seconds = perf_counter() - start
        report.update({
            "image": str(args.image), "image_size": [image.width, image.height],
            "model": MODEL_ID if args.depth_map is None else None,
            "depth_map_source": str(args.depth_map) if args.depth_map else None,
            "device": device,
            "timing_seconds": {
                "depth_load_or_inference": round(depth_seconds, 4),
                "analysis": round(analysis_seconds, 4),
            },
            "timing_note": "A primeira inferência inclui carregamento/download do modelo; não é benchmark de FPS.",
        })
        pixels = np.asarray(image).copy()
        pixels[mask] = (0.4 * pixels[mask] + 0.6 * np.array([255, 50, 50])).astype(np.uint8)
        overlay = Image.fromarray(pixels)
        roi = report["roi_pixels"]
        draw = ImageDraw.Draw(overlay)
        draw.rectangle((roi["left"], roi["top"], roi["right"] - 1, roi["bottom"] - 1),
                       outline="yellow", width=3)
        args.output.mkdir(parents=True, exist_ok=True)
        overlay.save(args.output / "overlay.png")
        Image.fromarray((normalized * 255).astype(np.uint8)).save(args.output / "depth.png")
        Image.fromarray(mask.astype(np.uint8) * 255).save(args.output / "candidates.png")
        np.save(args.output / "depth.npy", depth)
        (args.output / "report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError, ImportError, RuntimeError) as exc:
        parser.exit(1, f"Erro: {exc}\n")
    print(f"Resultado: {report['status']}")
    print(f"Área candidata na região frontal: {report['candidate_area_fraction']:.1%}")
    print(f"Arquivos salvos em: {args.output.resolve()}")


if __name__ == "__main__":
    main()
