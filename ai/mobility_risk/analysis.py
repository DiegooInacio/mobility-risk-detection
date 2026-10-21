"""Heurística de contraste lateral em profundidade relativa inversa."""

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

    def __post_init__(self):
        if not 0 < self.roi_left < self.roi_right < 1:
            raise ValueError("A região central deve deixar espaço para as laterais.")
        if not 0 <= self.roi_top < self.roi_bottom <= 1:
            raise ValueError("Limites verticais inválidos.")
        for value in (self.min_closeness, self.min_contrast, self.min_area_fraction):
            if not np.isfinite(value) or not 0 < value <= 1:
                raise ValueError("Os limiares devem estar em (0, 1].")


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
    if informative:
        normalized = np.clip((depth - low) / (high - low), 0, 1)
        # Compara pixels na mesma linha para reduzir o efeito do chão em perspectiva.
        sides = np.concatenate((normalized[top:bottom, :left],
                                normalized[top:bottom, right:]), axis=1)
        baseline = np.median(sides, axis=1, keepdims=True)
        center = normalized[top:bottom, left:right]
        mask[top:bottom, left:right] = (
            (center >= config.min_closeness)
            & (center - baseline >= config.min_contrast)
        )
    area_fraction = float(mask[top:bottom, left:right].mean())
    status = "inconclusivo"
    if informative:
        status = ("possivel_obstaculo" if area_fraction >= config.min_area_fraction
                  else "sem_indicio_pela_regra")
    report = {
        "status": status,
        "candidate_area_fraction": area_fraction,
        "roi_pixels": {"left": left, "top": top, "right": right, "bottom": bottom},
        "normalization": {"percentile_2": float(low), "percentile_98": float(high)},
        "config": asdict(config),
        "depth_kind": "relative_inverse_depth",
        "note": "Heurística experimental: ausência de indício não significa caminho seguro.",
    }
    return report, normalized, mask
