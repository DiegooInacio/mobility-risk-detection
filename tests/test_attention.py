import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from mobility_risk.attention import AttentionConfig, analyze_attention, expand_box
from mobility_risk.cli import main
from mobility_risk.objects import Instance, save_instances
from mobility_risk.occupancy import analyze_occupancy
from scripts.compare_attention import main as compare


class AttentionTests(unittest.TestCase):
    def test_margin_can_trigger_zone_without_mask_reaching_center(self):
        mask = np.zeros((100, 100), dtype=bool)
        mask[40:60, 60:80] = True
        instances = [Instance(mask, "chair", 0.9)]
        self.assertEqual(analyze_occupancy(mask.shape, instances)[0]["status"], "sem_ocupacao_pela_regra")
        no_margin, _, _ = analyze_attention(mask.shape, instances, AttentionConfig(margin_fraction=0))
        self.assertEqual(no_margin["status"], "sem_acionamento_pela_regra")
        expanded, zone, actual = analyze_attention(mask.shape, instances, AttentionConfig(margin_fraction=0.5))
        self.assertEqual(expanded["status"], "regiao_atencao_acionada")
        self.assertEqual(expanded["objects"][0]["expanded_bbox_pixels"],
                         {"left": 50, "top": 30, "right": 90, "bottom": 70})
        self.assertTrue(zone[45, 52])
        self.assertFalse(actual[45, 52])

    def test_expansion_rounds_outward_and_clips_to_image(self):
        box, margin = expand_box({"left": 0, "top": 0, "right": 11, "bottom": 11}, (20, 20), 0.15)
        self.assertEqual(margin, {"x": 2, "y": 2})
        self.assertEqual(box, {"left": 0, "top": 0, "right": 13, "bottom": 13})
        box, _ = expand_box({"left": 15, "top": 15, "right": 20, "bottom": 20}, (20, 20), 1)
        self.assertEqual(box, {"left": 10, "top": 10, "right": 20, "bottom": 20})

    def test_zero_margin_is_filled_box_not_segmentation_mask(self):
        mask = np.zeros((100, 100), dtype=bool)
        mask[40:60, 40] = True
        mask[40:60, 59] = True
        report, zone, actual = analyze_attention(mask.shape, [Instance(mask, "chair", 0.9)],
                                                AttentionConfig(margin_fraction=0))
        self.assertEqual(report["status"], "regiao_atencao_acionada")
        self.assertTrue(zone[50, 50])
        self.assertFalse(actual[50, 50])
        self.assertGreater(report["attention_area_fraction"], report["object_occupancy_area_fraction"])

    def test_unknown_or_low_confidence_stays_inconclusive(self):
        for instances in ([], [Instance(np.ones((100, 100), dtype=bool), "chair", 0.2)]):
            report, zone, _ = analyze_attention((100, 100), instances)
            self.assertEqual(report["status"], "inconclusivo")
            self.assertFalse(zone.any())

    def test_overlap_is_union_and_empty_or_distant_zone_does_not_trigger(self):
        mask = np.zeros((100, 100), dtype=bool)
        mask[40:60, 40:60] = True
        item = Instance(mask, "chair", 0.9)
        single = analyze_attention(mask.shape, [item])
        duplicate = analyze_attention(mask.shape, [item, item])
        np.testing.assert_array_equal(single[1], duplicate[1])
        self.assertEqual(single[0]["attention_area_fraction"], duplicate[0]["attention_area_fraction"])
        edge = np.zeros_like(mask)
        edge[:5, :5] = True
        self.assertEqual(analyze_attention(edge.shape, [Instance(edge, "chair", 0.9)])[0]["status"], "sem_acionamento_pela_regra")

    def test_invalid_margin_and_fractions(self):
        for value in (-1, 1.1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                AttentionConfig(margin_fraction=value)
        with self.assertRaises(ValueError):
            AttentionConfig(min_zone_overlap=0)

    def test_cli_and_comparison_skip_depth_and_keep_original_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            photo = root / "photo.png"
            Image.new("RGB", (100, 100)).save(photo)
            cache_folder = root / "cache/photo"
            cache_folder.mkdir(parents=True)
            cache = cache_folder / "instances.npz"
            mask = np.zeros((100, 100), dtype=bool)
            mask[40:60, 40:60] = True
            save_instances(cache, [Instance(mask, "chair", 0.9)], mask.shape,
                           hashlib.sha256(photo.read_bytes()).hexdigest(), {"inference_confidence": 0.15})
            before = cache.read_bytes()
            output = root / "single"
            with patch("mobility_risk.cli.estimate", side_effect=AssertionError("Sem profundidade")), \
                 patch("mobility_risk.cli.segment", side_effect=AssertionError("Usar cache")):
                main([str(photo), "--rule", "attention", "--instances", str(cache), "--output", str(output)])
                self.assertEqual({p.name for p in output.iterdir()},
                                 {"overlay.png", "attention.png", "objects.png", "instances.npz", "instances.meta.json", "report.json"})
                collection = root / "collection.json"
                collection.write_text(json.dumps({"images": [{"image": str(photo), "depth_map": "missing.npy"}]}))
                destination = root / "comparison"
                compare(["--collection", str(collection), "--instances-dir", str(root / "cache"), "--output", str(destination)])
                with (destination / "summary.csv").open() as handle:
                    rows = list(csv.DictReader(handle))
                self.assertEqual(len(rows), 4)
                self.assertEqual(list(destination.rglob("*.npy")), [])
                self.assertEqual(cache.read_bytes(), before)
                with self.assertRaises(SystemExit):
                    compare(["--collection", str(collection), "--instances-dir", str(root / "cache"), "--output", str(destination)])
            for args in (["--rule", "attention", "--max-distance-m", "2"],
                         ["--rule", "occupancy", "--attention-margin", "0.2"],
                         ["--rule", "attention", "--min-occupancy-fraction", "0.2"]):
                with self.assertRaises(SystemExit):
                    main([str(photo), *args])


if __name__ == "__main__":
    unittest.main()
