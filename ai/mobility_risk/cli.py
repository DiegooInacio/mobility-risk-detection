import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from .analysis import Config, analyze
from .attention import AttentionConfig, analyze_attention
from .depth import METRIC_MODEL_ID, MODEL_ID, estimate
from .metric import MetricConfig, analyze_metric
from .objects import (ObjectConfig, analyze_objects, combine_reports, load_instances,
                      save_instances, segment)
from .occupancy import OccupancyConfig, analyze_occupancy


def render_overlay(image, mask, report, min_confidence=None):
    pixels = np.asarray(image).copy()
    pixels[mask] = (0.4 * pixels[mask] + 0.6 * np.array([255, 50, 50])).astype(np.uint8)
    overlay = Image.fromarray(pixels)
    roi = report["roi_pixels"]
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((roi["left"], roi["top"], roi["right"] - 1, roi["bottom"] - 1),
                   outline="yellow", width=3)
    if min_confidence is not None:
        for obj in report["objects"]:
            if obj["bbox_pixels"] and obj["segmentation_confidence"] >= min_confidence:
                box = obj["bbox_pixels"]
                expanded = obj.get("expanded_bbox_pixels")
                if expanded:
                    x0, y0, x1, y1 = (expanded[key] for key in ("left", "top", "right", "bottom"))
                    for x in range(x0, x1, 20):
                        draw.line((x, y0, min(x + 11, x1 - 1), y0), fill="orange", width=3)
                        draw.line((x, y1 - 1, min(x + 11, x1 - 1), y1 - 1), fill="orange", width=3)
                    for y in range(y0, y1, 20):
                        draw.line((x0, y, x0, min(y + 11, y1 - 1)), fill="orange", width=3)
                        draw.line((x1 - 1, y, x1 - 1, min(y + 11, y1 - 1)), fill="orange", width=3)
                draw.rectangle((box["left"], box["top"], box["right"]-1, box["bottom"]-1),
                               outline="red" if obj["alert"] else "cyan", width=3)
                draw.text((box["left"] + 3, box["top"] + 3),
                          f"{obj['class_name']} {obj['segmentation_confidence']:.2f}",
                          fill="white", stroke_width=1, stroke_fill="black")
    return overlay


def run_spatial(args):
    attention = args.rule == "attention"
    incompatible = (args.depth_map, args.depth_kind, args.max_distance_m,
                    args.min_object_near_fraction, args.min_floor_gap_m,
                    args.min_component_fraction, args.decision_mode,
                    args.min_width_fraction, args.min_height_fraction,
                    args.min_closeness, args.min_contrast, args.min_area_fraction)
    if any(value is not None for value in incompatible):
        raise ValueError(f"A regra {args.rule} não usa mapas, profundidade, metros ou parâmetros das regras anteriores.")
    incompatible_artifacts = ["depth.npy", "depth.png", "depth.meta.json", "near.png"]
    incompatible_artifacts += ["occupancy.png"] if attention else ["attention.png", "objects.png"]
    if any((args.output / name).exists() for name in incompatible_artifacts):
        raise ValueError("O destino contém artefatos de outra abordagem. Escolha outra pasta.")
    config = AttentionConfig(
        margin_fraction=0.15 if args.attention_margin is None else args.attention_margin,
        min_confidence=0.35 if args.min_object_confidence is None else args.min_object_confidence,
        min_roi_fraction=0.01 if args.min_attention_fraction is None else args.min_attention_fraction,
        min_zone_overlap=0.10 if args.min_attention_overlap is None else args.min_attention_overlap,
        min_central_fraction=0.10 if args.min_attention_central_fraction is None else args.min_attention_central_fraction
    ) if attention else OccupancyConfig(
        min_confidence=0.35 if args.min_object_confidence is None else args.min_object_confidence,
        min_roi_fraction=0.01 if args.min_occupancy_fraction is None else args.min_occupancy_fraction,
        min_object_overlap=0.10 if args.min_occupancy_overlap is None else args.min_occupancy_overlap,
        min_central_fraction=0.10 if args.min_occupancy_central_fraction is None else args.min_occupancy_central_fraction)
    with Image.open(args.image) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
    shape = (image.height, image.width)
    image_sha256 = hashlib.sha256(args.image.read_bytes()).hexdigest()
    start = perf_counter()
    if args.instances:
        instances, metadata = load_instances(args.instances, shape, image_sha256, config.min_confidence)
    else:
        instances, metadata = segment(image, args.segment_model, args.device, min(0.15, config.min_confidence))
    segmentation_seconds = perf_counter() - start
    start = perf_counter()
    if attention:
        report, mask, object_mask = analyze_attention(shape, instances, config)
    else:
        report, mask = analyze_occupancy(shape, instances, config)
    report.update({
        "image": str(args.image), "image_size": [image.width, image.height], "image_sha256": image_sha256,
        "segmentation": {**metadata, "source": str(args.instances) if args.instances else None},
        "timing_seconds": {"analysis": round(perf_counter() - start, 4),
                           "segmentation_load_or_inference": round(segmentation_seconds, 4)},
        "timing_note": "Sem etapa de profundidade. Segmentação inclui carregamento/inferência ou leitura de instâncias; não é benchmark de FPS.",
    })
    args.output.mkdir(parents=True, exist_ok=True)
    render_overlay(image, mask, report, config.min_confidence).save(args.output / "overlay.png")
    Image.fromarray(mask.astype(np.uint8) * 255).save(args.output / ("attention.png" if attention else "occupancy.png"))
    if attention:
        Image.fromarray(object_mask.astype(np.uint8) * 255).save(args.output / "objects.png")
    save_instances(args.output / "instances.npz", instances, shape, image_sha256, metadata)
    (args.output / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Resultado: {report['status']}")
    if attention:
        print(f"Sobreposição da região de atenção: {report['attention_area_fraction']:.1%}")
        print(f"Instâncias que acionaram atenção: {report['diagnostics']['triggering_instance_count']}")
    else:
        print(f"Área ocupada na região frontal: {report['occupancy_area_fraction']:.1%}")
        print(f"Instâncias com ocupação frontal: {report['diagnostics']['occupying_instance_count']}")
    print(report["note"])
    print(f"Arquivos salvos em: {args.output.resolve()}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="POC de análise experimental de obstáculo frontal.")
    parser.add_argument("image", type=Path, help="Foto a analisar")
    parser.add_argument("--output", type=Path, default=Path("outputs/latest"))
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--depth-map", type=Path,
                        help="Reutiliza .npy; a unidade deve ser compatível com a regra")
    parser.add_argument("--depth-kind", choices=["relative_inverse_depth", "metric_m"],
                        help="Declara a unidade de um .npy externo sem metadados")
    parser.add_argument("--min-closeness", type=float)
    parser.add_argument("--rule", choices=["lateral", "floor", "metric", "objects", "hybrid", "occupancy", "attention"], default="lateral",
                        help="occupancy/attention usam só segmentação; demais regras usam profundidade")
    parser.add_argument("--min-contrast", type=float)
    parser.add_argument("--min-area-fraction", type=float)
    parser.add_argument("--max-distance-m", type=float)
    parser.add_argument("--min-floor-gap-m", type=float)
    parser.add_argument("--min-component-fraction", type=float)
    parser.add_argument("--decision-mode", choices=["area", "width"])
    parser.add_argument("--min-width-fraction", type=float)
    parser.add_argument("--min-height-fraction", type=float)
    parser.add_argument("--instances", type=Path, help="Reutiliza instâncias .npz da mesma imagem")
    parser.add_argument("--segment-model", type=Path, default=Path("outputs/models/yolo11n-seg.pt"))
    parser.add_argument("--min-object-confidence", type=float)
    parser.add_argument("--min-object-near-fraction", type=float)
    parser.add_argument("--min-occupancy-fraction", type=float, help="Fração mínima da ROI ocupada por uma instância")
    parser.add_argument("--min-occupancy-overlap", type=float, help="Fração mínima da máscara do objeto dentro da ROI")
    parser.add_argument("--min-occupancy-central-fraction", type=float, help="Suporte mínimo da máscara na faixa central")
    parser.add_argument("--attention-margin", type=float, help="Margem por lado como fração da largura/altura da caixa; padrão 0.15")
    parser.add_argument("--min-attention-fraction", type=float, help="Fração mínima da ROI coberta pela região de atenção")
    parser.add_argument("--min-attention-overlap", type=float, help="Fração mínima da caixa expandida dentro da ROI")
    parser.add_argument("--min-attention-central-fraction", type=float, help="Suporte mínimo da região de atenção no centro")
    args = parser.parse_args(argv)
    try:
        if args.rule != "occupancy" and any(value is not None for value in (
                args.min_occupancy_fraction, args.min_occupancy_overlap, args.min_occupancy_central_fraction)):
            raise ValueError("Parâmetros de ocupação exigem --rule occupancy.")
        if args.rule != "attention" and any(value is not None for value in (
                args.attention_margin, args.min_attention_fraction, args.min_attention_overlap,
                args.min_attention_central_fraction)):
            raise ValueError("Parâmetros de região de atenção exigem --rule attention.")
        if args.rule in ("occupancy", "attention"):
            return run_spatial(args)
        object_rule = args.rule in ("objects", "hybrid")
        metric = args.rule in ("metric", "objects", "hybrid")
        min_area = 0.05 if args.min_area_fraction is None else args.min_area_fraction
        if not object_rule and (args.instances or args.min_object_confidence is not None
                                or args.min_object_near_fraction is not None):
            raise ValueError("Parâmetros de instâncias exigem --rule objects ou hybrid.")
        if args.rule == "objects" and any(value is not None for value in
                (args.min_floor_gap_m, args.min_component_fraction, args.min_area_fraction,
                 args.decision_mode, args.min_width_fraction, args.min_height_fraction)):
            raise ValueError("A regra objects não usa perfil do chão, componentes ou decisão por área/largura.")
        expected_kind = "metric_m" if metric else "relative_inverse_depth"
        if metric:
            if args.min_closeness is not None or args.min_contrast is not None:
                raise ValueError("A regra metric usa --max-distance-m e --min-floor-gap-m, não limiares relativos.")
            config = MetricConfig(
                max_distance_m=2.0 if args.max_distance_m is None else args.max_distance_m,
                min_floor_gap_m=0.30 if args.min_floor_gap_m is None else args.min_floor_gap_m,
                min_component_fraction=0.01 if args.min_component_fraction is None else args.min_component_fraction,
                min_area_fraction=min_area,
                decision_mode=args.decision_mode or "area",
                min_width_fraction=0.30 if args.min_width_fraction is None else args.min_width_fraction,
                min_height_fraction=0.02 if args.min_height_fraction is None else args.min_height_fraction)
        else:
            if any(value is not None for value in (args.max_distance_m, args.min_floor_gap_m,
                                                   args.min_component_fraction, args.decision_mode,
                                                   args.min_width_fraction, args.min_height_fraction)):
                raise ValueError("Parâmetros métricos exigem --rule metric.")
            config = Config(min_closeness=0.60 if args.min_closeness is None else args.min_closeness,
                            min_contrast=0.15 if args.min_contrast is None else args.min_contrast,
                            min_area_fraction=min_area, rule=args.rule)
        object_config = ObjectConfig(
            max_distance_m=config.max_distance_m,
            min_confidence=0.35 if args.min_object_confidence is None else args.min_object_confidence,
            min_near_fraction=0.10 if args.min_object_near_fraction is None else args.min_object_near_fraction
        ) if object_rule else None
        if args.depth_kind and not args.depth_map:
            raise ValueError("--depth-kind só é usado com --depth-map.")
        with Image.open(args.image) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
        image_sha256 = hashlib.sha256(args.image.read_bytes()).hexdigest()
        start = perf_counter()
        source_model = None
        if args.depth_map:
            metadata_path = args.depth_map.with_suffix(".meta.json")
            legacy_report = args.depth_map.parent / "report.json"
            metadata = None
            if metadata_path.is_file():
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            elif args.depth_map.name == "depth.npy" and legacy_report.is_file():
                metadata = json.loads(legacy_report.read_text(encoding="utf-8"))
            declared = metadata.get("depth_kind") if metadata is not None else args.depth_kind
            if metadata is not None and args.depth_kind and declared != args.depth_kind:
                raise ValueError("--depth-kind contradiz os metadados do mapa.")
            if declared is None and metric:
                raise ValueError("Mapa sem metadados: declare --depth-kind metric_m apenas se os valores forem metros.")
            if declared is not None and declared != expected_kind:
                raise ValueError(f"Mapa {declared} incompatível com a regra {args.rule} ({expected_kind}).")
            source_model = metadata.get("model") if metadata is not None else None
            if metadata and metadata.get("image_sha256") and metadata["image_sha256"] != image_sha256:
                raise ValueError("O mapa salvo pertence a outra imagem.")
            depth = np.load(args.depth_map, allow_pickle=False)
            device = "precomputed"
        else:
            depth, device = estimate(image, args.device, METRIC_MODEL_ID if metric else MODEL_ID)
        depth_seconds = perf_counter() - start
        if depth.shape != (image.height, image.width):
            raise ValueError("O mapa deve ter as dimensões da foto após correção da orientação EXIF.")
        start = perf_counter()
        segmentation_seconds = 0.0
        instances = instance_metadata = near_mask = None
        if object_rule:
            segmentation_start = perf_counter()
            if args.instances:
                instances, instance_metadata = load_instances(
                    args.instances, depth.shape, image_sha256, object_config.min_confidence)
            else:
                instances, instance_metadata = segment(
                    image, args.segment_model, args.device, min(0.15, object_config.min_confidence))
            segmentation_seconds = perf_counter() - segmentation_start
            report, normalized, mask, near_mask = analyze_objects(depth, instances, object_config)
            if args.rule == "hybrid":
                metric_report, _, metric_mask = analyze_metric(depth, config)
                report, mask = combine_reports(metric_report, report, metric_mask, mask)
            report["segmentation"] = {**instance_metadata,
                                      "source": str(args.instances) if args.instances else None}
        else:
            report, normalized, mask = analyze_metric(depth, config) if metric else analyze(depth, config)
        analysis_seconds = perf_counter() - start
        report.update({
            "image": str(args.image), "image_size": [image.width, image.height],
            "model": (METRIC_MODEL_ID if metric else MODEL_ID) if args.depth_map is None else None,
            "depth_map_source": str(args.depth_map) if args.depth_map else None,
            "source_model": source_model,
            "device": device,
            "timing_seconds": {
                "depth_load_or_inference": round(depth_seconds, 4),
                "analysis": round(analysis_seconds - segmentation_seconds, 4),
                "segmentation_load_or_inference": round(segmentation_seconds, 4),
            },
            "timing_note": (
                "Profundidade lida do arquivo. O tempo de segmentação é separado e inclui carregamento/inferência ou leitura do cache; não é benchmark de FPS."
                if args.depth_map and object_rule else
                "Profundidade e segmentação têm tempos separados, incluindo carregamento dos modelos; não é benchmark de FPS."
                if object_rule else
                "Mapa reutilizado: mede leitura do arquivo, sem inferência do modelo."
                if args.depth_map else
                "A primeira inferência inclui carregamento/download do modelo; não é benchmark de FPS."
            ),
        })
        overlay = render_overlay(image, mask, report, object_config.min_confidence if object_rule else None)
        args.output.mkdir(parents=True, exist_ok=True)
        overlay.save(args.output / "overlay.png")
        Image.fromarray((normalized * 255).astype(np.uint8)).save(args.output / "depth.png")
        Image.fromarray(mask.astype(np.uint8) * 255).save(args.output / "candidates.png")
        np.save(args.output / "depth.npy", depth)
        if object_rule:
            save_instances(args.output / "instances.npz", instances, depth.shape,
                           image_sha256, instance_metadata)
            Image.fromarray(near_mask.astype(np.uint8) * 255).save(args.output / "near.png")
        (args.output / "depth.meta.json").write_text(json.dumps({
            "depth_kind": report["depth_kind"], "model": report["model"] or source_model,
            "image_size": [image.width, image.height],
            "image_sha256": image_sha256,
        }, indent=2) + "\n", encoding="utf-8")
        (args.output / "report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError, ImportError, RuntimeError) as exc:
        parser.exit(1, f"Erro: {exc}\n")
    print(f"Resultado: {report['status']}")
    print(f"Área candidata na região frontal: {report['candidate_area_fraction']:.1%}")
    diagnostic = report["diagnostics"]
    if object_rule:
        print(f"Instâncias detectadas: {diagnostic['detected_instance_count']}")
        print(f"Instâncias com alerta: {diagnostic['alert_instance_count']}")
        if args.rule == "hybrid":
            print(f"Ramo geométrico: {report['branches']['metric']['status']}")
        print(report["coverage"])
    elif metric:
        print(f"Passou por proximidade: {diagnostic['closeness_pass_fraction']:.2%}")
        print(f"Critério de decisão: {report['decision']['mode']}")
        print(f"Regiões mantidas: {diagnostic['kept_component_count']}")
        print(f"Referência do chão: {diagnostic['reason']}")
    elif diagnostic["contrast_pass_fraction"] is not None:
        print(f"Passou por proximidade: {diagnostic['closeness_pass_fraction']:.2%}")
        print(f"Passou por contraste ({args.rule}): {diagnostic['contrast_pass_fraction']:.2%}")
    else:
        print(f"Contraste indisponível: {diagnostic['reason']}")
    print(f"Arquivos salvos em: {args.output.resolve()}")


if __name__ == "__main__":
    main()
