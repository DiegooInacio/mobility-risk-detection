"""Região de atenção 2D: caixa expandida e sobreposição com a região frontal."""

from dataclasses import asdict, dataclass
import math

import numpy as np

from .objects import roi_geometry, spatial_evidence
from .occupancy import OccupancyConfig


@dataclass(frozen=True)
class AttentionConfig:
    margin_fraction: float = 0.15
    min_confidence: float = 0.35
    min_roi_fraction: float = 0.01
    min_zone_overlap: float = 0.10
    min_central_fraction: float = 0.10

    def __post_init__(self):
        if not np.isfinite(self.margin_fraction) or not 0 <= self.margin_fraction <= 1:
            raise ValueError("A margem deve estar entre 0 e 1 (fração por lado da caixa).")
        for name, value in asdict(self).items():
            if name != "margin_fraction" and (not np.isfinite(value) or not 0 < value <= 1):
                raise ValueError(f"{name} deve estar em (0, 1].")


def expand_box(box, image_shape, fraction):
    """15% significa adicionar 15% da largura/altura em cada lado, antes do recorte."""
    height, width = image_shape
    dx = math.ceil((box["right"] - box["left"]) * fraction)
    dy = math.ceil((box["bottom"] - box["top"]) * fraction)
    return {"left": max(0, box["left"] - dx), "top": max(0, box["top"] - dy),
            "right": min(width, box["right"] + dx), "bottom": min(height, box["bottom"] + dy)}, {"x": dx, "y": dy}


def analyze_attention(image_shape, instances, config=AttentionConfig()):
    geometry = roi_geometry(image_shape)
    roi, central = geometry["roi"], geometry["central"]
    selected_zones = np.zeros(image_shape, dtype=bool)
    selected_objects = np.zeros(image_shape, dtype=bool)
    min_pixels = max(1, int(np.ceil(roi.sum() * config.min_roi_fraction)))
    objects = []
    for index, instance in enumerate(instances):
        evidence, actual_inside = spatial_evidence(
            instance, index, geometry, OccupancyConfig(min_confidence=config.min_confidence))
        # As medidas da máscara são informativas; a decisão usa a caixa expandida.
        evidence.pop("rejection_reasons")
        zone = np.zeros(image_shape, dtype=bool)
        expanded, margins = None, {"x": 0, "y": 0}
        if evidence["bbox_pixels"]:
            expanded, margins = expand_box(evidence["bbox_pixels"], image_shape, config.margin_fraction)
            zone[expanded["top"]:expanded["bottom"], expanded["left"]:expanded["right"]] = True
        inside = zone & roi
        zone_count, inside_count = int(zone.sum()), int(inside.sum())
        overlap = inside_count / zone_count if zone_count else 0.0
        center_fraction = int((inside & central).sum()) / inside_count if inside_count else 0.0
        reasons = []
        if instance.confidence < config.min_confidence:
            reasons.append("low_segmentation_confidence")
        if inside_count < min_pixels:
            reasons.append("insufficient_zone_roi_pixels")
        if overlap < config.min_zone_overlap:
            reasons.append("zone_mostly_outside_roi")
        if center_fraction < config.min_central_fraction:
            reasons.append("zone_outside_central_strip")
        accepted = not reasons
        if accepted:
            selected_zones |= inside
            selected_objects |= actual_inside
        objects.append({
            **evidence, "expanded_bbox_pixels": expanded, "margin_pixels": margins,
            "zone_pixel_count": zone_count, "zone_roi_pixel_count": inside_count,
            "zone_roi_overlap_fraction": overlap, "zone_central_fraction": center_fraction,
            "zone_roi_area_fraction": inside_count / int(roi.sum()),
            "attention_triggered": accepted, "alert": accepted, "rejection_reasons": reasons,
        })
    confident = any(item.confidence >= config.min_confidence for item in instances)
    report = {
        "rule": "attention", "requires_depth": False, "depth_kind": None, "config": asdict(config),
        "status": "regiao_atencao_acionada" if selected_zones.any() else
                  "sem_acionamento_pela_regra" if confident else "inconclusivo",
        "attention_area_fraction": float(selected_zones[roi].mean()),
        "object_occupancy_area_fraction": float(selected_objects[roi].mean()),
        "roi_pixels": geometry["roi_pixels"], "central_strip_pixels": geometry["central_strip_pixels"],
        "diagnostics": {"detected_instance_count": len(objects),
                        "triggering_instance_count": sum(item["attention_triggered"] for item in objects),
                        "min_zone_roi_pixels": min_pixels,
                        "reason": "expanded_boxes_evaluated" if confident else
                                  "no_confident_instances" if instances else "no_detected_instances"},
        "objects": objects,
        "coverage": "Somente instâncias reconhecidas; a margem é uma região 2D e não garante cobertura de obstáculos.",
        "note": "Sobreposição de caixa expandida na imagem. Não determina aproximação, distância física ou risco de colisão.",
    }
    return report, selected_zones, selected_objects
