"""Heurísticas experimentais em profundidade relativa inversa."""

from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class Config:
    roi_left: float = 0.35
    roi_right: float = 0.65
    roi_top: float = 0.30
    roi_bottom: float = 0.80
    min_closeness: float = 0.60
    min_contrast: float = 0.15
    min_area_fraction: float = 0.05
    rule: str = "lateral"

    def __post_init__(self):
        if self.rule not in ("lateral", "floor"):
            raise ValueError("Regra deve ser lateral ou floor.")
        if not 0 < self.roi_left < self.roi_right < 1:
            raise ValueError("A região central deve deixar espaço para as laterais.")
        if not 0 <= self.roi_top < self.roi_bottom <= 1:
            raise ValueError("Limites verticais inválidos.")
        for value in (self.min_closeness, self.min_contrast, self.min_area_fraction):
            if not np.isfinite(value) or not 0 < value <= 1:
                raise ValueError("Os limiares devem estar em (0, 1].")


def floor_reference(normalized, left, right, bottom):
    """Ajusta d_inversa = a*y+b ao trecho central abaixo da ROI.

    Hipótese: essa faixa contém predominantemente chão plano. Não é segmentação
    de chão; obstáculos na faixa, câmera inclinada e escadas invalidam a hipótese.
    Os limites abaixo são experimentais e ficam registrados no relatório.
    """
    height = normalized.shape[0]
    details = {"sample_top": bottom, "sample_bottom": height,
               "sample_left": left, "sample_right": right,
               "min_samples": 8, "min_slope": 0.05, "max_median_residual": 0.05}
    if height - bottom < details["min_samples"]:
        return None, {**details, "valid": False, "reason": "insufficient_bottom_rows"}
    y = np.arange(bottom, height) / (height - 1)
    samples = np.median(normalized[bottom:, left:right], axis=1)
    slope, intercept = np.polyfit(y, samples, 1)
    residual = float(np.median(np.abs(samples - (slope * y + intercept))))
    valid = bool(slope >= details["min_slope"] and residual <= details["max_median_residual"])
    details.update({"valid": valid, "slope": float(slope), "intercept": float(intercept),
                    "median_residual": residual,
                    "reason": "fit_accepted" if valid else "bottom_profile_not_supported"})
    if not valid:
        return None, details
    # Extrapolação do plano do chão para as linhas superiores da imagem.
    reference = np.clip(slope * np.arange(height) / (height - 1) + intercept, 0, 1)
    return reference[:, None], details


def analyze(depth: np.ndarray, config: Config = Config()):
    """Valores maiores significam mais perto; não aceita distâncias em metros.

    A normalização é por imagem. O escore não é probabilidade nem distância.
    Retorna relatório, mapa normalizado e máscara de candidatos.
    """
    depth = np.asarray(depth, dtype=np.float32)
    if depth.ndim != 2 or min(depth.shape) < 16:
        raise ValueError("O mapa deve ser bidimensional e ter pelo menos 16x16 pixels.")
    if not np.isfinite(depth).all():
        raise ValueError("O mapa contém NaN ou infinito.")
    height, width = depth.shape
    left, right = int(width * config.roi_left), int(width * config.roi_right)
    top, bottom = int(height * config.roi_top), int(height * config.roi_bottom)
    if not 0 < left < right < width or not 0 <= top < bottom <= height:
        raise ValueError("A região configurada não cabe na resolução do mapa.")
    low, high = np.percentile(depth, [2, 98])
    informative = bool(high - low > np.finfo(np.float32).eps)
    normalized = np.zeros_like(depth)
    mask = np.zeros_like(depth, dtype=bool)
    center_shape = (bottom - top, right - left)
    close_mask = np.zeros(center_shape, dtype=bool)
    contrast_mask = np.zeros(center_shape, dtype=bool)
    floor_fit = None
    reference_available = informative
    contrast = np.zeros(center_shape, dtype=np.float32)
    if informative:
        normalized = np.clip((depth - low) / (high - low), 0, 1)
        # Compara pixels na mesma linha para reduzir o efeito do chão em perspectiva.
        sides = np.concatenate((normalized[top:bottom, :left],
                                normalized[top:bottom, right:]), axis=1)
        center = normalized[top:bottom, left:right]
        close_mask = center >= config.min_closeness
        if config.rule == "lateral":
            baseline = np.median(sides, axis=1, keepdims=True)
        else:
            reference, floor_fit = floor_reference(normalized, left, right, bottom)
            reference_available = reference is not None
            baseline = reference[top:bottom] if reference_available else None
        if reference_available:
            contrast = center - baseline
            contrast_mask = contrast >= config.min_contrast
            mask[top:bottom, left:right] = close_mask & contrast_mask
    area_fraction = float(mask[top:bottom, left:right].mean())
    status = "inconclusivo"
    if informative and reference_available:
        status = ("possivel_obstaculo" if area_fraction >= config.min_area_fraction
                  else "sem_indicio_pela_regra")
    report = {
        "status": status,
        "candidate_area_fraction": area_fraction,
        "rule": config.rule,
        "diagnostics": {
            "roi_pixel_count": int(close_mask.size),
            "closeness_pass_fraction": float(close_mask.mean()),
            "contrast_pass_fraction": float(contrast_mask.mean()) if reference_available else None,
            "both_pass_fraction": area_fraction if reference_available else None,
            "contrast_percentiles": dict(zip(
                ("p50", "p90", "p99", "max"),
                map(float, np.percentile(contrast, [50, 90, 99, 100]))
            )) if informative and reference_available else None,
            "reference_available": bool(reference_available),
            "reason": ("low_depth_variation" if not informative else
                       "reference_unavailable" if not reference_available else
                       "criteria_evaluated"),
        },
        "floor_fit": floor_fit,
        "roi_pixels": {"left": left, "top": top, "right": right, "bottom": bottom},
        "normalization": {"percentile_2": float(low), "percentile_98": float(high)},
        "config": asdict(config),
        "depth_kind": "relative_inverse_depth",
        "note": "Heurística experimental: ausência de indício não significa caminho seguro.",
    }
    return report, normalized, mask
