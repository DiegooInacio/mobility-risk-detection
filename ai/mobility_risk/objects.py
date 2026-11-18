"""Decisão experimental por instância segmentada e profundidade métrica.

As máscaras identificam apenas classes conhecidas pelo segmentador. Paredes e
objetos não reconhecidos não são descartados como seguros por esta abordagem.
"""

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

import numpy as np

from .analysis import Config

SEGMENT_MODEL = "yolo11n-seg.pt"


@dataclass
class Instance:
    mask: np.ndarray
    class_name: str
    confidence: float


@dataclass(frozen=True)
class ObjectConfig:
    max_distance_m: float = 2.0
    min_confidence: float = 0.35
    min_near_fraction: float = 0.10
    min_roi_fraction: float = 0.01
    min_object_overlap: float = 0.10
    min_central_fraction: float = 0.10

    def __post_init__(self):
        if not np.isfinite(self.max_distance_m) or self.max_distance_m <= 0:
            raise ValueError("A distância deve ser positiva e finita.")
        for name, value in asdict(self).items():
            if name != "max_distance_m" and (not np.isfinite(value) or not 0 < value <= 1):
                raise ValueError(f"{name} deve estar em (0, 1].")


def roi_geometry(image_shape):
    if len(image_shape) != 2 or min(image_shape) < 16:
        raise ValueError("A imagem deve ter pelo menos 16x16 pixels.")
    height, width = image_shape
    geometry = Config()
    left, right = int(width * geometry.roi_left), int(width * geometry.roi_right)
    top, bottom = int(height * geometry.roi_top), int(height * geometry.roi_bottom)
    central_left = left + int((right - left) * 0.4)
    central_right = max(central_left + 1, left + int((right - left) * 0.6))
    roi = np.zeros(image_shape, dtype=bool)
    roi[top:bottom, left:right] = True
    central = np.zeros_like(roi)
    central[top:bottom, central_left:central_right] = True
    return {"roi": roi, "central": central,
            "roi_pixels": {"left": left, "right": right, "top": top, "bottom": bottom},
            "central_strip_pixels": {"left": central_left, "right": central_right}}


def spatial_evidence(instance, index, geometry, config):
    """Critérios espaciais compartilhados; não recebe nem estima profundidade."""
    roi, central = geometry["roi"], geometry["central"]
    mask = np.asarray(instance.mask)
    if mask.shape != roi.shape or mask.dtype != bool:
        raise ValueError("Cada máscara deve ser booleana e ter as dimensões da imagem.")
    if not np.isfinite(instance.confidence) or not 0 <= instance.confidence <= 1:
        raise ValueError("Confiança de instância inválida.")
    total = int(mask.sum())
    inside = mask & roi
    count = int(inside.sum())
    min_pixels = max(1, int(np.ceil(roi.sum() * config.min_roi_fraction)))
    overlap = count / total if total else 0.0
    central_fraction = int((inside & central).sum()) / count if count else 0.0
    reasons = []
    if instance.confidence < config.min_confidence:
        reasons.append("low_segmentation_confidence")
    if count < min_pixels:
        reasons.append("insufficient_roi_pixels")
    if overlap < config.min_object_overlap:
        reasons.append("mostly_outside_roi")
    if central_fraction < config.min_central_fraction:
        reasons.append("outside_central_strip")
    coords = np.argwhere(mask)
    return {
        "instance_index": index, "class_name": str(instance.class_name),
        "segmentation_confidence": float(instance.confidence),
        "mask_pixel_count": total, "roi_pixel_count": count,
        "roi_overlap_fraction": overlap, "central_fraction": central_fraction,
        "roi_area_fraction": count / int(roi.sum()),
        "image_area_fraction": total / roi.size,
        "rejection_reasons": reasons,
        "bbox_pixels": {"left": int(coords[:, 1].min()), "right": int(coords[:, 1].max()) + 1,
                        "top": int(coords[:, 0].min()), "bottom": int(coords[:, 0].max()) + 1}
                       if total else None,
    }, inside


def analyze_objects(depth, instances, config=ObjectConfig()):
    depth = np.asarray(depth, dtype=np.float32)
    if depth.ndim != 2 or min(depth.shape) < 16 or not np.isfinite(depth).all() or np.any(depth <= 0):
        raise ValueError("Profundidade deve ser um mapa 2D em metros, positivo e finito, de pelo menos 16x16.")
    geometry = roi_geometry(depth.shape)
    roi = geometry["roi"]
    min_pixels = max(1, int(np.ceil(roi.sum() * config.min_roi_fraction)))
    alerts, near = np.zeros_like(roi), np.zeros_like(roi)
    objects = []
    for index, instance in enumerate(instances):
        evidence, inside = spatial_evidence(instance, index, geometry, config)
        count = evidence["roi_pixel_count"]
        close = inside & (depth <= config.max_distance_m)
        close_count = int(close.sum())
        near_fraction = close_count / count if count else 0.0
        reasons = evidence["rejection_reasons"]
        if near_fraction < config.min_near_fraction:
            reasons.append("insufficient_near_fraction")
        accepted = not reasons
        if accepted:
            # Agrupa a instância, inclusive partes desconectadas, sem preencher os buracos.
            alerts |= inside
            near |= close
        objects.append({
            **evidence,
            "near_fraction": near_fraction, "alert": accepted, "rejection_reasons": reasons,
            "estimated_depth_p10_m": float(np.percentile(depth[inside], 10)) if count else None,
            "estimated_depth_median_m": float(np.median(depth[inside])) if count else None,
        })
    has_alert = bool(alerts.any())
    confident = any(item.confidence >= config.min_confidence for item in instances)
    report = {
        "rule": "objects", "depth_kind": "metric_m", "config": asdict(config),
        "status": "possivel_obstaculo" if has_alert else
                  "sem_indicio_pela_regra" if confident else "inconclusivo",
        "roi_pixels": geometry["roi_pixels"],
        "candidate_area_fraction": float(alerts[roi].mean()),
        "diagnostics": {"detected_instance_count": len(objects),
                        "alert_instance_count": sum(obj["alert"] for obj in objects),
                        "min_roi_pixels": min_pixels,
                        "near_pixel_fraction": float(near[roi].mean()),
                        "reason": "instances_evaluated" if confident else
                                  "no_confident_instances" if instances else "no_detected_instances"},
        "central_strip_pixels": geometry["central_strip_pixels"],
        "objects": objects,
        "coverage": "Somente instâncias detectadas das classes conhecidas; ausência de objeto não atesta segurança.",
        "note": "Distâncias estimadas. Confiança do segmentador não é probabilidade de colisão. Sem teste semântico de chão/parede.",
    }
    visual = np.clip(1 - depth / config.max_distance_m, 0, 1)
    return report, visual, alerts, near


def combine_reports(metric_report, object_report, metric_mask, object_mask):
    """União conservadora: preserva alertas geométricos, mesmo sem classe reconhecida."""
    from copy import deepcopy

    result = deepcopy(object_report)
    result["rule"] = "hybrid"
    statuses = [metric_report["status"], object_report["status"]]
    result["status"] = ("possivel_obstaculo" if "possivel_obstaculo" in statuses else
                        "inconclusivo" if "inconclusivo" in statuses else "sem_indicio_pela_regra")
    # Um ramo só contribui para a marcação do alerta se sua decisão for positiva.
    metric_alert = metric_mask if metric_report["status"] == "possivel_obstaculo" else np.zeros_like(metric_mask)
    mask = metric_alert | object_mask
    roi = result["roi_pixels"]
    result["candidate_area_fraction"] = float(mask[roi["top"]:roi["bottom"], roi["left"]:roi["right"]].mean())
    result["branches"] = {"metric": metric_report, "objects": object_report}
    result["config"] = {"metric": metric_report["config"], "objects": object_report["config"]}
    result["coverage"] = "União dos alertas geométricos e por objetos; não é garantia de cobertura ou segurança."
    return result, mask


def segment(image, model_path, device="auto", inference_confidence=0.15):
    import torch
    from ultralytics import YOLO

    selected = ("0" if torch.cuda.is_available() else "cpu") if device == "auto" else ("0" if device == "cuda" else device)
    model_path = Path(model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(model_path))
    if model.task != "segment":
        raise ValueError("--segment-model deve indicar pesos de segmentação de instâncias.")
    prediction = model.predict(image, conf=inference_confidence, retina_masks=True,
                               imgsz=640, device=selected, verbose=False)[0]
    instances = []
    if prediction.masks is not None:
        masks = prediction.masks.data.cpu().numpy() >= 0.5
        for mask, box in zip(masks, prediction.boxes):
            if mask.shape != (image.height, image.width):
                raise ValueError("Segmentador retornou máscaras fora da resolução original.")
            instances.append(Instance(mask, prediction.names[int(box.cls.item())], float(box.conf.item())))
    return instances, {"model": str(model_path), "architecture": model_path.name,
                       "weights_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
                       "inference_confidence": inference_confidence, "imgsz": 640,
                       "device": selected}


def save_instances(path, instances, image_shape, image_sha256, metadata):
    path = Path(path)
    masks = np.stack([item.mask for item in instances]) if instances else np.empty((0, *image_shape), dtype=bool)
    np.savez_compressed(path, masks=masks,
                        confidences=np.array([item.confidence for item in instances]),
                        class_names=np.array([item.class_name for item in instances], dtype="U"))
    path.with_suffix(".meta.json").write_text(json.dumps({
        **metadata, "image_sha256": image_sha256, "image_shape": list(image_shape),
    }, indent=2) + "\n", encoding="utf-8")


def load_instances(path, image_shape, image_sha256, min_confidence):
    path = Path(path)
    metadata = json.loads(path.with_suffix(".meta.json").read_text(encoding="utf-8"))
    if metadata["image_sha256"] != image_sha256 or metadata["image_shape"] != list(image_shape):
        raise ValueError("As máscaras salvas não correspondem à imagem informada.")
    if min_confidence < metadata["inference_confidence"]:
        raise ValueError("O cache foi gerado com confiança mínima maior; execute a segmentação novamente.")
    with np.load(path, allow_pickle=False) as data:
        masks, scores, names = data["masks"], data["confidences"], data["class_names"]
        if masks.dtype != bool or masks.shape != (len(scores), *image_shape) or len(names) != len(scores):
            raise ValueError("Cache de instâncias inválido.")
        instances = [Instance(mask, str(name), float(score)) for mask, name, score in zip(masks, names, scores)]
    return instances, metadata
