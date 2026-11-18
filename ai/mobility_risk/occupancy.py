"""Ocupação frontal em imagens 2D, sem profundidade ou inferência de distância."""

from dataclasses import asdict, dataclass

import numpy as np

from .objects import roi_geometry, spatial_evidence


@dataclass(frozen=True)
class OccupancyConfig:
    min_confidence: float = 0.35
    min_roi_fraction: float = 0.01
    min_object_overlap: float = 0.10
    min_central_fraction: float = 0.10

    def __post_init__(self):
        for name, value in asdict(self).items():
            if not np.isfinite(value) or not 0 < value <= 1:
                raise ValueError(f"{name} deve estar em (0, 1].")


def analyze_occupancy(image_shape, instances, config=OccupancyConfig()):
    """Recebe só dimensões e máscaras; não aceita mapas ou unidades de distância."""
    geometry = roi_geometry(image_shape)
    roi = geometry["roi"]
    occupied = np.zeros(image_shape, dtype=bool)
    objects = []
    for index, instance in enumerate(instances):
        evidence, inside = spatial_evidence(instance, index, geometry, config)
        accepted = not evidence["rejection_reasons"]
        if accepted:
            occupied |= inside
        objects.append({**evidence, "occupies_frontal_region": accepted, "alert": accepted})
    has_occupancy = bool(occupied.any())
    confident = any(item.confidence >= config.min_confidence for item in instances)
    fraction = float(occupied[roi].mean())
    report = {
        "rule": "occupancy", "requires_depth": False, "depth_kind": None,
        "config": asdict(config),
        "status": "ocupacao_frontal_detectada" if has_occupancy else
                  "sem_ocupacao_pela_regra" if confident else "inconclusivo",
        "occupancy_area_fraction": fraction,
        "roi_pixels": geometry["roi_pixels"],
        "central_strip_pixels": geometry["central_strip_pixels"],
        "diagnostics": {
            "detected_instance_count": len(objects),
            "occupying_instance_count": sum(item["occupies_frontal_region"] for item in objects),
            "min_roi_pixels": max(1, int(np.ceil(roi.sum() * config.min_roi_fraction))),
            "reason": "spatial_criteria_evaluated" if confident else
                      "no_confident_instances" if instances else "no_detected_instances",
        },
        "objects": objects,
        "coverage": "Somente instâncias reconhecidas. Sem ocupação detectada não significa passagem livre.",
        "note": "Alerta de ocupação na imagem, sem estimar proximidade física, metros ou probabilidade de colisão.",
    }
    return report, occupied
