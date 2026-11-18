import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from mobility_risk.objects import Instance
from scripts.compare_objects import main


class CompareObjectsTests(unittest.TestCase):
    def test_six_profiles_share_one_segmentation_and_keep_input_map(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            photo, depth_path = root / "photo.png", root / "depth.npy"
            Image.new("RGB", (100, 100)).save(photo)
            mask = np.zeros((100, 100), dtype=bool)
            mask[40:60, 40:60] = True
            depth = np.full((100, 100), 3.5)
            depth[mask] = 0.7
            np.save(depth_path, depth)
            depth_path.with_suffix(".meta.json").write_text(json.dumps({"depth_kind": "metric_m"}))
            collection = root / "collection.json"
            collection.write_text(json.dumps({"images": [{"image": str(photo), "depth_map": str(depth_path)}]}))
            output = root / "output"
            with patch("mobility_risk.cli.segment", return_value=(
                [Instance(mask, "chair", 0.9)], {"model": "test", "inference_confidence": 0.15}
            )) as segment:
                main(["--collection", str(collection), "--output", str(output)])
                self.assertEqual(segment.call_count, 1)
            with (output / "summary.csv").open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 6)
            self.assertEqual(len({row["profile"] for row in rows}), 6)
            np.testing.assert_array_equal(np.load(depth_path), depth)
            for row in rows:
                if row["profile"].startswith(("objects-", "hybrid-")):
                    self.assertEqual(row["status"], "possivel_obstaculo")
            self.assertTrue((output / "run.json").is_file())
            self.assertEqual(len(list((output / "source_snapshot").iterdir())), 7)


if __name__ == "__main__":
    unittest.main()
