import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from mobility_risk.analysis import Config, analyze
from mobility_risk.cli import main


def floor_map():
    # Mesmo perfil em todas as colunas: chão mais próximo na parte inferior.
    return np.broadcast_to(np.linspace(0, 1, 100)[:, None], (100, 100)).copy()


class AnalysisTests(unittest.TestCase):
    def test_floor_gradient_does_not_trigger(self):
        report, _, mask = analyze(floor_map())
        self.assertEqual(report["status"], "sem_indicio_pela_regra")
        self.assertFalse(mask.any())

    def test_central_obstacle_triggers_and_is_affine_invariant(self):
        depth = floor_map()
        depth[35:65, 40:60] = 2
        first, _, mask = analyze(depth)
        second, _, _ = analyze(3 * depth + 7)
        self.assertEqual(first["status"], "possivel_obstaculo")
        self.assertAlmostEqual(first["candidate_area_fraction"], second["candidate_area_fraction"])
        self.assertTrue(mask[40, 50])
        self.assertFalse(mask[:, :35].any())

    def test_lateral_obstacle_does_not_trigger(self):
        depth = floor_map()
        depth[35:65, 5:25] = 2
        self.assertEqual(analyze(depth)[0]["status"], "sem_indicio_pela_regra")

    def test_flat_map_is_inconclusive(self):
        self.assertEqual(analyze(np.ones((100, 100)))[0]["status"], "inconclusivo")

    def test_diagnostics_separate_closeness_and_contrast(self):
        depth = floor_map()
        depth[35:65, :] += 0.8  # Região próxima também nas laterais.
        report, _, _ = analyze(depth, Config(min_closeness=0.2))
        diagnostic = report["diagnostics"]
        self.assertGreater(diagnostic["closeness_pass_fraction"], 0)
        self.assertEqual(diagnostic["contrast_pass_fraction"], 0)
        self.assertEqual(diagnostic["both_pass_fraction"], 0)
        self.assertEqual(diagnostic["roi_pixel_count"], 1500)

    def test_floor_rule_rejects_linear_floor_and_detects_raised_region(self):
        config = Config(rule="floor", min_closeness=0.2)
        clear, _, _ = analyze(floor_map(), config)
        self.assertEqual(clear["status"], "sem_indicio_pela_regra")
        self.assertTrue(clear["floor_fit"]["valid"])
        depth = floor_map()
        depth[35:65, 40:60] += 0.6
        obstacle, _, _ = analyze(depth, config)
        self.assertEqual(obstacle["status"], "possivel_obstaculo")
        transformed, _, _ = analyze(depth * 3 + 7, config)
        self.assertAlmostEqual(obstacle["candidate_area_fraction"],
                               transformed["candidate_area_fraction"])

    def test_floor_rule_handles_near_lateral_surfaces(self):
        depth = floor_map()
        depth[:80, :35] += 0.6
        depth[:80, 65:] += 0.6
        depth[35:65, 40:60] += 0.6
        lateral, _, _ = analyze(depth, Config(min_closeness=0.2))
        floor, _, _ = analyze(depth, Config(rule="floor", min_closeness=0.2))
        self.assertEqual(lateral["status"], "sem_indicio_pela_regra")
        self.assertEqual(floor["status"], "possivel_obstaculo")

    def test_floor_rule_is_inconclusive_without_supported_ground_profile(self):
        depth = floor_map()
        depth[80:, :] = 0.9
        report, _, _ = analyze(depth, Config(rule="floor"))
        self.assertEqual(report["status"], "inconclusivo")
        self.assertFalse(report["diagnostics"]["reference_available"])
        self.assertIsNone(report["diagnostics"]["contrast_pass_fraction"])
        self.assertFalse(report["floor_fit"]["valid"])
        tiny, _, _ = analyze(floor_map()[:20, :20], Config(rule="floor"))
        self.assertEqual(tiny["floor_fit"]["reason"], "insufficient_bottom_rows")

    def test_invalid_data_and_thresholds_are_rejected(self):
        for invalid in (np.zeros((5, 5)), np.zeros((20, 20, 3)), np.full((20, 20), np.nan)):
            with self.assertRaises(ValueError):
                analyze(invalid)
        with self.assertRaises(ValueError):
            Config(min_area_fraction=0)
        with self.assertRaises(ValueError):
            Config(rule="unknown")

    def test_cli_saves_reusable_artifacts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = root / "input.png"
            depth_path = root / "input.npy"
            output = root / "results"
            Image.new("RGB", (100, 100), "gray").save(image)
            depth = floor_map()
            depth[35:65, 40:60] = 2
            np.save(depth_path, depth)
            main([str(image), "--depth-map", str(depth_path), "--output", str(output)])
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(report["status"], "possivel_obstaculo")
            for name in ("overlay.png", "depth.png", "candidates.png", "depth.npy"):
                self.assertTrue((output / name).is_file())
            np.testing.assert_array_equal(np.load(output / "depth.npy"), depth)
            floor_output = root / "floor"
            main([str(image), "--depth-map", str(depth_path), "--rule", "floor",
                  "--min-closeness", "0.2", "--output", str(floor_output)])
            floor_report = json.loads((floor_output / "report.json").read_text())
            self.assertEqual(floor_report["rule"], "floor")
            self.assertEqual(floor_report["status"], "possivel_obstaculo")
            self.assertTrue(floor_report["floor_fit"]["valid"])
            self.assertEqual(floor_report["diagnostics"]["both_pass_fraction"],
                             floor_report["candidate_area_fraction"])


if __name__ == "__main__":
    unittest.main()
