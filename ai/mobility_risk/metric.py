"""Análise métrica experimental: proximidade, referência do chão e regiões conexas."""

from dataclasses import asdict, dataclass

import numpy as np

from .analysis import Config


@dataclass(frozen=True)
class MetricConfig:
    max_distance_m: float = 2.0
    min_floor_gap_m: float = 0.30
    min_component_fraction: float = 0.01
    min_area_fraction: float = 0.05
    decision_mode: str = "area"
    min_width_fraction: float = 0.30
    min_height_fraction: float = 0.02

    def __post_init__(self):
        if self.decision_mode not in ("area", "width"):
            raise ValueError("decision_mode deve ser area ou width.")
        for value in (self.max_distance_m, self.min_floor_gap_m):
            if not np.isfinite(value) or value <= 0:
                raise ValueError("Os limiares em metros devem ser positivos e finitos.")
        for value in (self.min_component_fraction, self.min_area_fraction,
                      self.min_width_fraction, self.min_height_fraction):
            if not np.isfinite(value) or not 0 < value <= 1:
                raise ValueError("As frações de área devem estar em (0, 1].")


def connected_regions(mask, depth, min_pixels, offset,
                      min_width_fraction=0.30, min_height_fraction=0.02):
    """Componentes com conectividade 4 por intervalos horizontais e union-find.

    Evita uma dependência extra e uma busca Python por cada pixel da fotografia.
    """
    parents, runs = [], []

    def root(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    previous = []
    for y, row in enumerate(mask):
        transitions = np.diff(np.pad(row.astype(np.int8), (1, 1)))
        starts, ends = np.flatnonzero(transitions == 1), np.flatnonzero(transitions == -1)
        current = []
        previous_index = 0
        for start, end in zip(starts.tolist(), ends.tolist()):
            index = len(parents)
            parents.append(index)
            runs.append((y, start, end, index))
            current.append((start, end, index))
            while previous_index < len(previous) and previous[previous_index][1] <= start:
                previous_index += 1
            j = previous_index
            while j < len(previous) and previous[j][0] < end:
                parents[root(previous[j][2])] = root(index)
                j += 1
        previous = current
    groups = {}
    for y, start, end, index in runs:
        groups.setdefault(root(index), []).append((y, start, end))
    kept = np.zeros_like(mask)
    regions = []
    for group in groups.values():
        count = sum(end - start for _, start, end in group)
        if count < min_pixels:
            continue
        for y, start, end in group:
            kept[y, start:end] = True
        values = np.concatenate([depth[y, start:end] for y, start, end in group])
        left, top = offset
        # Usa pixels efetivamente presentes por linha, não a largura da caixa.
        row_pixels = np.zeros(mask.shape[0], dtype=int)
        central_pixels = np.zeros(mask.shape[0], dtype=int)
        central_left = int(mask.shape[1] * 0.4)
        central_right = max(central_left + 1, int(mask.shape[1] * 0.6))
        for y, start, end in group:
            row_pixels[y] += end - start
            central_pixels[y] += max(0, min(end, central_right) - max(start, central_left))
        supported_rows = ((row_pixels / mask.shape[1] >= min_width_fraction)
                          & (central_pixels / (central_right - central_left) >= 0.5))
        longest = current_run = 0
        for supported_row in supported_rows:
            current_run = current_run + 1 if supported_row else 0
            longest = max(longest, current_run)
        min_rows = max(2, int(np.ceil(min_height_fraction * mask.shape[0])))
        regions.append({
            "pixel_count": count,
            "bbox_pixels": {"left": left + min(run[1] for run in group),
                            "top": top + min(run[0] for run in group),
                            "right": left + max(run[2] for run in group),
                            "bottom": top + max(run[0] for run in group) + 1},
            "estimated_depth_p10_m": float(np.percentile(values, 10)),
            "estimated_depth_median_m": float(np.median(values)),
            "width_support": {
                "max_row_occupancy_fraction": float(row_pixels.max() / mask.shape[1]),
                "longest_supported_band_rows": longest,
                "min_band_rows": min_rows,
                "passes": bool(longest >= min_rows),
            },
        })
    regions.sort(key=lambda region: region["pixel_count"], reverse=True)
    return kept, regions, len(groups)


def analyze_metric(depth, config=MetricConfig()):
    """Entrada exclusivamente em metros. A normalização só produz a visualização.

    O perfil linear é ajustado em 1/metros, sem percentis por imagem, e compara
    profundidade ao longo da visão; o gap não é altura acima do chão.
    """
    depth = np.asarray(depth, dtype=np.float32)
    if depth.ndim != 2 or min(depth.shape) < 16:
        raise ValueError("O mapa métrico deve ser 2D e ter pelo menos 16x16 pixels.")
    if not np.isfinite(depth).all() or np.any(depth <= 0):
        raise ValueError("O mapa métrico deve conter apenas distâncias positivas e finitas.")
    height, width = depth.shape
    geometry = Config()
    left, right = int(width * geometry.roi_left), int(width * geometry.roi_right)
    top, bottom = int(height * geometry.roi_top), int(height * geometry.roi_bottom)
    center = depth[top:bottom, left:right]
    close = center <= config.max_distance_m
    raw = np.zeros_like(close)
    mask = np.zeros_like(depth, dtype=bool)
    fit = {"sample_top": bottom, "sample_bottom": height, "sample_left": left,
           "sample_right": right, "min_samples": 8,
           "min_slope_inverse_m": 0.02, "max_median_residual_inverse_m": 0.02,
           "valid": False, "reason": "insufficient_bottom_rows"}
    supported = np.zeros((bottom - top, 1), dtype=bool)
    if height - bottom >= fit["min_samples"]:
        y = np.arange(bottom, height) / (height - 1)
        inverse_samples = np.median(1.0 / depth[bottom:, left:right].astype(np.float64), axis=1)
        slope, intercept = np.polyfit(y, inverse_samples, 1)
        residual = float(np.median(np.abs(inverse_samples - (slope * y + intercept))))
        fit.update({"slope_inverse_m": float(slope), "intercept_inverse_m": float(intercept),
                    "median_residual_inverse_m": residual})
        valid = bool(slope >= fit["min_slope_inverse_m"]
                     and residual <= fit["max_median_residual_inverse_m"])
        fit.update({"valid": valid, "reason": "fit_accepted" if valid else "bottom_profile_not_supported"})
        if valid:
            floor_inverse = (slope * np.arange(top, bottom) / (height - 1) + intercept)[:, None]
            supported = floor_inverse > 1e-6
            floor_m = np.zeros_like(floor_inverse)
            np.divide(1.0, floor_inverse, out=floor_m, where=supported)
            raw = close & supported & (floor_m - center >= config.min_floor_gap_m)
    available = bool(fit["valid"] and supported.any())
    min_pixels = max(1, int(np.ceil(config.min_component_fraction * center.size)))
    kept, regions, raw_count = connected_regions(
        raw, center, min_pixels, (left, top), config.min_width_fraction, config.min_height_fraction)
    mask[top:bottom, left:right] = kept
    area = float(kept.mean())
    area_pass = bool(area >= config.min_area_fraction)
    width_pass = any(region["width_support"]["passes"] for region in regions)
    alert = area_pass if config.decision_mode == "area" else width_pass
    reason = "criteria_evaluated" if available else "floor_reference_unavailable"
    report = {
        "status": ("possivel_obstaculo" if alert else
                   "sem_indicio_pela_regra") if available else "inconclusivo",
        "rule": "metric", "depth_kind": "metric_m", "config": asdict(config),
        "candidate_area_fraction": area,
        "decision": {
            "mode": config.decision_mode,
            "area_pass": area_pass if available else None,
            "width_pass": width_pass if available else None,
            "width_policy": {
                "central_strip_left_fraction": 0.4, "central_strip_right_fraction": 0.6,
                "min_central_strip_occupancy": 0.5,
                "min_consecutive_rows": max(2, int(np.ceil(config.min_height_fraction * center.shape[0]))),
                "note": "Cada componente é avaliado separadamente; a máscara mostra todos os candidatos mantidos.",
            },
        },
        "roi_pixels": {"left": left, "right": right, "top": top, "bottom": bottom},
        "diagnostics": {
            "roi_pixel_count": center.size, "closeness_pass_fraction": float(close.mean()),
            "contrast_pass_fraction": None,
            "floor_supported_fraction": float(supported.mean()),
            "both_pass_fraction": float(raw.mean()) if available else None,
            "raw_candidate_area_fraction": float(raw.mean()) if available else None,
            "filtered_candidate_area_fraction": area,
            "raw_component_count": raw_count, "kept_component_count": len(regions),
            "min_component_pixels": min_pixels,
            "reference_available": available, "reason": reason,
        },
        "floor_fit": fit, "regions": regions,
        "visualization": {"kind": "fixed_metric_scale", "near_m": 0,
                          "far_m": config.max_distance_m, "brighter_is_closer": True},
        "note": ("Distâncias estimadas, sem calibração. O perfil do chão é uma hipótese; "
                 "gap é diferença de profundidade, não altura física. Ausência de alerta não atesta segurança."),
    }
    visual = np.clip(1 - depth / config.max_distance_m, 0, 1)
    return report, visual, mask
