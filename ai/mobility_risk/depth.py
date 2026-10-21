"""Adaptador do modelo, carregado apenas quando necessário."""

import numpy as np

MODEL_ID = "depth-anything/Depth-Anything-V2-Small-hf"


def estimate(image, device="auto"):
    import torch
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation

    selected = ("cuda" if torch.cuda.is_available() else "cpu") if device == "auto" else device
    processor = AutoImageProcessor.from_pretrained(MODEL_ID)
    model = AutoModelForDepthEstimation.from_pretrained(MODEL_ID).to(selected).eval()
    inputs = processor(images=image, return_tensors="pt").to(selected)
    with torch.inference_mode():
        prediction = model(**inputs).predicted_depth
        resized = torch.nn.functional.interpolate(
            prediction.unsqueeze(1), size=(image.height, image.width),
            mode="bicubic", align_corners=False,
        )
    if selected.startswith("cuda"):
        torch.cuda.synchronize()
    return resized[0, 0].cpu().numpy().astype(np.float32), selected
