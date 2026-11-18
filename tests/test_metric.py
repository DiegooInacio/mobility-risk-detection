import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from mobility_risk.cli import main
from mobility_risk.depth import METRIC_MODEL_ID
from mobility_risk.metric import MetricConfig, analyze_metric, connected_regions


def metric_floor():
    y = np.arange(100) / 99
    return np.broadcast_to((1 / (0.2 + y))[:, None], (100, 100)).copy()


class MetricTests(unittest.TestCase):
    def test_close_floor_alone_does_not_trigger(self):
        report, _, mask = analyze_metric(metric_floor())
        self.assertTrue(report["floor_fit"]["valid"])
        self.assertGreater(report["diagnostics"]["closeness_pass_fraction"], 0)
        self.assertFalse(mask.any())
        self.assertEqual(report["status"], "sem_indicio_pela_regra")

    def test_metric_obstacle_has_region_and_depth_statistics(self):
        depth = metric_floor()
        depth[35:65, 40:60] = 0.7
        report, _, mask = analyze_metric(depth)
        self.assertEqual(report["status"], "possivel_obstaculo")
        self.assertEqual(report["depth_kind"], "metric_m")
        self.assertEqual(report["regions"][0]["pixel_count"], 600)
        self.assertAlmostEqual(report["regions"][0]["estimated_depth_median_m"], 0.7)
        self.assertEqual(report["regions"][0]["bbox_pixels"],
                         {"left": 40, "top": 35, "right": 60, "bottom": 65})
        self.assertFalse(mask[:, :35].any())

    def test_distance_threshold_uses_meters_and_not_image_percentiles(self):
        depth = metric_floor() * 4
        depth[35:65, 40:60] = 2.5
        report, visual, _ = analyze_metric(depth)
        self.assertEqual(report["status"], "sem_indicio_pela_regra")
        self.assertEqual(visual[40, 50], 0)
        report, _, _ = analyze_metric(depth, MetricConfig(max_distance_m=3))
        self.assertEqual(report["status"], "possivel_obstaculo")

    def test_small_regions_are_removed_and_lateral_surfaces_do_not_change_decision(self):
        depth = metric_floor()
        depth[35:37, 40:42] = 0.7
        report, _, mask = analyze_metric(depth)
        self.assertEqual(report["diagnostics"]["raw_component_count"], 1)
        self.assertEqual(report["diagnostics"]["kept_component_count"], 0)
        self.assertFalse(mask.any())
        depth[35:65, 40:60] = 0.7
        first = analyze_metric(depth)[0]
        depth[:, :35] = 0.2
        depth[:, 65:] = 0.2
        second = analyze_metric(depth)[0]
        self.assertEqual(first["candidate_area_fraction"], second["candidate_area_fraction"])

    def test_unsupported_ground_is_inconclusive(self):
        report, _, mask = analyze_metric(np.ones((100, 100)))
        self.assertEqual(report["status"], "inconclusivo")
        self.assertFalse(report["diagnostics"]["reference_available"])
        self.assertIsNone(report["diagnostics"]["raw_candidate_area_fraction"])
        self.assertFalse(mask.any())
        report, _, _ = analyze_metric(np.ones((20, 20)))
        self.assertEqual(report["floor_fit"]["reason"], "insufficient_bottom_rows")

    def test_connected_regions_merge_bridges_but_not_diagonal_pixels(self):
        mask = np.array([[1, 0, 1], [1, 1, 1], [0, 0, 0]], dtype=bool)
        kept, regions, count = connected_regions(mask, np.ones((3, 3)), 1, (0, 0))
        self.assertEqual(count, 1)
        self.assertEqual(regions[0]["pixel_count"], 5)
        np.testing.assert_array_equal(kept, mask)
        _, regions, count = connected_regions(np.eye(3, dtype=bool), np.ones((3, 3)), 1, (0, 0))
        self.assertEqual(count, 3)
        self.assertEqual(len(regions), 3)

    def test_invalid_maps_and_parameters(self):
        for depth in (np.zeros((20, 20)), np.full((20, 20), -1),
                      np.full((20, 20), np.inf), np.ones((20, 20, 3))):
            with self.assertRaises(ValueError):
                analyze_metric(depth)
        for kwargs in ({"max_distance_m": 0}, {"min_floor_gap_m": float("nan")},
                       {"min_component_fraction": 2}):
            with self.assertRaises(ValueError):
                MetricConfig(**kwargs)
        for kwargs in ({"decision_mode": "unknown"}, {"min_width_fraction": 0},
                       {"min_height_fraction": float("nan")}):
            with self.assertRaises(ValueError):
                MetricConfig(**kwargs)

    def test_width_detects_small_central_band_without_five_percent_area(self):
        depth = metric_floor()
        depth[45:48, 42:58] = 0.7  # 3,2% da ROI, mas larga no centro.
        original, _, original_mask = analyze_metric(depth)
        alternative, _, alternative_mask = analyze_metric(depth, MetricConfig(decision_mode="width"))
        self.assertEqual(original["status"], "sem_indicio_pela_regra")
        self.assertEqual(alternative["status"], "possivel_obstaculo")
        self.assertFalse(alternative["decision"]["area_pass"])
        self.assertTrue(alternative["decision"]["width_pass"])
        np.testing.assert_array_equal(original_mask, alternative_mask)

    def test_width_rejects_thin_vertical_and_offcenter_regions(self):
        for rows, cols in ((slice(35, 75), slice(49, 51)),
                           (slice(35, 65), slice(35, 45))):
            depth = metric_floor()
            depth[rows, cols] = 0.7
            report, _, _ = analyze_metric(depth, MetricConfig(decision_mode="width"))
            self.assertGreater(report["diagnostics"]["kept_component_count"], 0)
            self.assertEqual(report["status"], "sem_indicio_pela_regra")

    def test_width_requires_consecutive_rows_and_actual_pixels_not_bbox(self):
        mask = np.zeros((50, 30), dtype=bool)
        mask[10:30, 14] = True
        mask[10, 5:25] = True
        mask[29, 5:25] = True
        # A caixa é larga e alta, mas só duas linhas isoladas possuem largura.
        _, regions, _ = connected_regions(mask, np.ones_like(mask, dtype=float), 1, (0, 0))
        self.assertFalse(regions[0]["width_support"]["passes"])
        self.assertEqual(regions[0]["width_support"]["longest_supported_band_rows"], 1)

    def test_cli_metadata_and_incompatible_units(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image, depth_path = root / "image.png", root / "metric.npy"
            Image.new("RGB", (100, 100)).save(image)
            depth = metric_floor()
            depth[35:65, 40:60] = 0.7
            np.save(depth_path, depth)
            base = [str(image), "--depth-map", str(depth_path), "--rule", "metric"]
            with self.assertRaises(SystemExit):
                main(base)  # Arquivo externo sem declaração de unidade.
            output = root / "output"
            main(base + ["--depth-kind", "metric_m", "--output", str(output)])
            metadata = json.loads((output / "depth.meta.json").read_text())
            self.assertEqual(metadata["depth_kind"], "metric_m")
            np.testing.assert_array_equal(np.load(output / "depth.npy"), depth)
            with self.assertRaises(SystemExit):
                main([str(image), "--depth-map", str(output / "depth.npy")])
            with self.assertRaises(SystemExit):
                main(base + ["--depth-kind", "relative_inverse_depth"])
            with self.assertRaises(SystemExit):
                main(base + ["--min-closeness", "0.2"])

    def test_cli_selects_metric_model_and_preserves_metadata_on_reuse(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            photo = root / "photo.png"
            Image.new("RGB", (100, 100)).save(photo)
            destination = root / "output"
            with patch("mobility_risk.cli.estimate", return_value=(metric_floor(), "cpu")) as estimate:
                main([str(photo), "--rule", "metric", "--output", str(destination)])
                estimate.assert_called_once()
                self.assertEqual(estimate.call_args.args[2], METRIC_MODEL_ID)
            reused = root / "reused"
            main([str(photo), "--rule", "metric", "--depth-map", str(destination / "depth.npy"),
                  "--output", str(reused)])
            report = json.loads((reused / "report.json").read_text())
            self.assertIsNone(report["model"])
            self.assertEqual(report["source_model"], METRIC_MODEL_ID)
            self.assertEqual(json.loads((reused / "depth.meta.json").read_text())["model"], METRIC_MODEL_ID)


if __name__ == "__main__":
    unittest.main()
