import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from mobility_risk.cli import main
from mobility_risk.metric import analyze_metric
from mobility_risk.objects import (Instance, ObjectConfig, analyze_objects,
                                   combine_reports, load_instances, save_instances)


def fragmented_instance():
    mask = np.zeros((100, 100), dtype=bool)
    mask[45:48, 40:50] = True
    mask[49:52, 50:60] = True
    return Instance(mask, "chair", 0.9)


class ObjectTests(unittest.TestCase):
    def test_instance_groups_disconnected_parts_without_filling_holes(self):
        item = fragmented_instance()
        depth = np.full((100, 100), 3.0)
        depth[item.mask] = 0.7
        report, _, mask, near = analyze_objects(depth, [item])
        self.assertEqual(report["status"], "possivel_obstaculo")
        self.assertEqual(report["objects"][0]["mask_pixel_count"], 60)
        self.assertLess(report["candidate_area_fraction"], 0.05)
        np.testing.assert_array_equal(mask, item.mask)
        np.testing.assert_array_equal(near, item.mask)
        self.assertFalse(mask[48, 50])

    def test_lateral_instances_do_not_alert_even_when_near(self):
        mask = np.zeros((100, 100), dtype=bool)
        mask[40:60, 60:85] = True
        report, _, marked, _ = analyze_objects(np.ones((100, 100)), [Instance(mask, "chair", 0.9)])
        self.assertEqual(report["status"], "sem_indicio_pela_regra")
        self.assertIn("outside_central_strip", report["objects"][0]["rejection_reasons"])
        self.assertFalse(marked.any())

    def test_overlapping_predictions_do_not_double_count_marked_area(self):
        item = fragmented_instance()
        report, _, marked, _ = analyze_objects(np.ones((100, 100)), [item, item])
        self.assertEqual(report["diagnostics"]["alert_instance_count"], 2)
        self.assertEqual(int(marked.sum()), 60)
        self.assertEqual(report["candidate_area_fraction"], 0.04)

    def test_near_fraction_is_per_instance_not_global_area(self):
        mask = np.zeros((100, 100), dtype=bool)
        mask[40:50, 40:60] = True
        item = Instance(mask, "chair", 0.9)
        depth = np.full((100, 100), 3.0)
        depth[40, 40:59] = 1.0  # 19 de 200 pixels, abaixo de 10%.
        self.assertEqual(analyze_objects(depth, [item])[0]["status"], "sem_indicio_pela_regra")
        depth[40, 59] = 1.0
        report = analyze_objects(depth, [item])[0]
        self.assertEqual(report["status"], "possivel_obstaculo")
        self.assertEqual(report["objects"][0]["near_fraction"], 0.1)

    def test_no_or_low_confidence_instances_are_inconclusive(self):
        depth = np.ones((100, 100))
        self.assertEqual(analyze_objects(depth, [])[0]["status"], "inconclusivo")
        item = fragmented_instance()
        item.confidence = 0.2
        report = analyze_objects(depth, [item])[0]
        self.assertEqual(report["status"], "inconclusivo")
        self.assertEqual(report["diagnostics"]["reason"], "no_confident_instances")

    def test_hybrid_preserves_geometry_alert_without_known_object(self):
        depth = np.broadcast_to((1 / (0.2 + np.arange(100)/99))[:, None], (100, 100)).copy()
        depth[35:65, 40:60] = 0.7
        metric, _, metric_mask = analyze_metric(depth)
        objects, _, objects_mask, _ = analyze_objects(depth, [])
        report, mask = combine_reports(metric, objects, metric_mask, objects_mask)
        self.assertEqual(report["status"], "possivel_obstaculo")
        self.assertEqual(report["rule"], "hybrid")
        np.testing.assert_array_equal(mask, metric_mask)

    def test_hybrid_does_not_turn_unknown_coverage_into_clear_result(self):
        depth = np.ones((100, 100))
        objects, _, mask, _ = analyze_objects(depth, [])
        metric, _, metric_mask = analyze_metric(depth)
        result, _ = combine_reports(metric, objects, metric_mask, mask)
        self.assertEqual(result["status"], "inconclusivo")

    def test_cache_checks_image_identity_and_inference_threshold(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "instances.npz"
            save_instances(path, [fragmented_instance()], (100, 100), "photo-a",
                           {"inference_confidence": 0.15, "model": "test"})
            items, meta = load_instances(path, (100, 100), "photo-a", 0.35)
            self.assertEqual(items[0].class_name, "chair")
            self.assertEqual(meta["model"], "test")
            with self.assertRaises(ValueError):
                load_instances(path, (100, 100), "photo-b", 0.35)
            with self.assertRaises(ValueError):
                load_instances(path, (100, 100), "photo-a", 0.10)
            save_instances(path, [], (100, 100), "photo-a", {"inference_confidence": 0.15})
            self.assertEqual(load_instances(path, (100, 100), "photo-a", 0.35)[0], [])

    def test_invalid_masks_and_parameters(self):
        with self.assertRaises(ValueError):
            ObjectConfig(min_near_fraction=0)
        for mask in (np.ones((100, 100)), np.ones((20, 20), dtype=bool)):
            with self.assertRaises(ValueError):
                analyze_objects(np.ones((100, 100)), [Instance(mask, "chair", 0.9)])

    def test_cli_cached_instances_and_objects_or_hybrid_without_models(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            photo = root / "photo.png"
            Image.new("RGB", (100, 100)).save(photo)
            item = fragmented_instance()
            depth = np.full((100, 100), 3.0)
            depth[item.mask] = 0.7
            with patch("mobility_risk.cli.estimate", return_value=(depth, "cpu")), \
                 patch("mobility_risk.cli.segment", return_value=(
                     [item], {"model": "test", "inference_confidence": 0.15})):
                main([str(photo), "--rule", "objects", "--output", str(root / "objects")])
            main([str(photo), "--rule", "hybrid", "--depth-map", str(root / "objects/depth.npy"),
                  "--instances", str(root / "objects/instances.npz"), "--output", str(root / "hybrid")])
            result = json.loads((root / "hybrid/report.json").read_text())
            self.assertEqual(result["status"], "possivel_obstaculo")
            self.assertTrue((root / "hybrid/near.png").is_file())
            self.assertEqual(result["branches"]["objects"]["objects"][0]["class_name"], "chair")


if __name__ == "__main__":
    unittest.main()
