import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from mobility_risk.cli import main
from mobility_risk.objects import Instance, ObjectConfig, analyze_objects, save_instances
from mobility_risk.occupancy import OccupancyConfig, analyze_occupancy


def central_instance():
    mask = np.zeros((100, 100), dtype=bool)
    mask[40:60, 40:60] = True
    return Instance(mask, "chair", 0.9)


class OccupancyTests(unittest.TestCase):
    def test_occupancy_detects_central_object_without_distance(self):
        item = central_instance()
        report, mask = analyze_occupancy((100, 100), [item])
        self.assertEqual(report["status"], "ocupacao_frontal_detectada")
        self.assertFalse(report["requires_depth"])
        self.assertIsNone(report["depth_kind"])
        self.assertEqual(report["objects"][0]["image_area_fraction"], 0.04)
        np.testing.assert_array_equal(mask, item.mask)
        encoded = json.dumps(report)
        self.assertNotIn("near_fraction", encoded)
        self.assertNotIn("estimated_depth", encoded)
        # Mesmo objeto distante é rejeitado pela análise métrica, mas ocupa a imagem.
        metric, _, _, _ = analyze_objects(np.full((100, 100), 20.0), [item], ObjectConfig())
        self.assertEqual(metric["status"], "sem_indicio_pela_regra")

    def test_no_or_unreliable_instances_remain_inconclusive(self):
        self.assertEqual(analyze_occupancy((100, 100), [])[0]["status"], "inconclusivo")
        item = central_instance()
        item.confidence = 0.2
        self.assertEqual(analyze_occupancy((100, 100), [item])[0]["status"], "inconclusivo")

    def test_lateral_and_small_objects_are_rejected(self):
        for rows, cols in ((slice(40, 60), slice(60, 85)), (slice(40, 42), slice(49, 51))):
            mask = np.zeros((100, 100), dtype=bool)
            mask[rows, cols] = True
            report, marked = analyze_occupancy((100, 100), [Instance(mask, "chair", 0.9)])
            self.assertEqual(report["status"], "sem_ocupacao_pela_regra")
            self.assertFalse(marked.any())

    def test_overlapping_predictions_are_unioned_and_area_is_reported_per_object(self):
        item = central_instance()
        report, mask = analyze_occupancy((100, 100), [item, item])
        self.assertEqual(int(mask.sum()), 400)
        self.assertEqual(report["diagnostics"]["occupying_instance_count"], 2)
        self.assertAlmostEqual(report["occupancy_area_fraction"], 400 / 1500)

    def test_invalid_dimensions_masks_and_configuration(self):
        with self.assertRaises(ValueError):
            analyze_occupancy((5, 5), [])
        with self.assertRaises(ValueError):
            analyze_occupancy((100, 100), [Instance(np.ones((100, 100)), "chair", 0.9)])
        with self.assertRaises(ValueError):
            OccupancyConfig(min_roi_fraction=float("nan"))

    def test_cached_cli_does_not_load_models_or_write_depth_artifacts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            photo, cache = root / "photo.png", root / "instances.npz"
            Image.new("RGB", (100, 100)).save(photo)
            save_instances(cache, [central_instance()], (100, 100),
                           hashlib.sha256(photo.read_bytes()).hexdigest(),
                           {"model": "test", "inference_confidence": 0.15})
            output = root / "output"
            with patch("mobility_risk.cli.estimate", side_effect=AssertionError("Profundidade não deve executar")), \
                 patch("mobility_risk.cli.segment", side_effect=AssertionError("Cache deve ser reutilizado")):
                main([str(photo), "--rule", "occupancy", "--instances", str(cache), "--output", str(output)])
            self.assertEqual({p.name for p in output.iterdir()},
                             {"overlay.png", "occupancy.png", "instances.npz", "instances.meta.json", "report.json"})
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(report["status"], "ocupacao_frontal_detectada")
            for flag in ("--max-distance-m", "--min-object-near-fraction", "--min-area-fraction"):
                with self.assertRaises(SystemExit):
                    main([str(photo), "--rule", "occupancy", flag, "0.5"])
            (output / "depth.npy").touch()
            with self.assertRaises(SystemExit):
                main([str(photo), "--rule", "occupancy", "--output", str(output)])

    def test_live_segmentation_route_also_skips_depth_model(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            photo = root / "photo.png"
            Image.new("RGB", (100, 100)).save(photo)
            with patch("mobility_risk.cli.estimate", side_effect=AssertionError("Sem profundidade")), \
                 patch("mobility_risk.cli.segment", return_value=(
                     [central_instance()], {"model": "test", "inference_confidence": 0.15})) as segment:
                main([str(photo), "--rule", "occupancy", "--output", str(root / "output")])
                self.assertEqual(segment.call_count, 1)


if __name__ == "__main__":
    unittest.main()
