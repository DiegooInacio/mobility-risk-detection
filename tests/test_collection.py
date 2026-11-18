import csv
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from scripts.evaluate_collection import digest, main


class CollectionTests(unittest.TestCase):
    def test_comparison_preserves_maps_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            photo = root / "scene.jpeg"
            Image.new("RGB", (100, 100)).save(photo)
            maps = root / "maps" / "scene"
            maps.mkdir(parents=True)
            y = np.arange(100) / 99
            depth = np.broadcast_to((1 / (0.2 + y))[:, None], (100, 100)).copy()
            np.save(maps / "depth.npy", depth)
            (maps / "depth.meta.json").write_text(json.dumps({"depth_kind": "metric_m"}))
            before = digest(maps / "depth.npy")
            collection = root / "collection.json"
            collection.write_text(json.dumps({"images": [{"image": str(photo)}]}))
            output = root / "comparison"
            args = ["--collection", str(collection), "--maps-dir", str(root / "maps"),
                    "--output", str(output)]
            main(args)
            with (output / "summary.csv").open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 3)
            self.assertEqual({row["max_distance_m"] for row in rows}, {"2.0", "2.5", "3.0"})
            self.assertTrue(all(row["status"] == "sem_indicio_pela_regra" for row in rows))
            run = json.loads((output / "run.json").read_text())
            self.assertEqual(run["inputs"][0]["depth_sha256"], before)
            self.assertEqual(digest(maps / "depth.npy"), before)
            self.assertEqual(len(list((output / "source_snapshot").iterdir())), 6)
            summary_before = digest(output / "summary.csv")
            with self.assertRaises(SystemExit):
                main(args)
            self.assertEqual(digest(output / "summary.csv"), summary_before)


if __name__ == "__main__":
    unittest.main()
