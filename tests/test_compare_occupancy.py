import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from mobility_risk.objects import Instance, save_instances
from scripts.compare_occupancy import main


class CompareOccupancyTests(unittest.TestCase):
    def test_comparison_needs_only_cached_instances_and_reference_csv(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            photo = root / "photo.png"
            Image.new("RGB", (100, 100)).save(photo)
            cache = root / "cache/photo"
            cache.mkdir(parents=True)
            mask = np.zeros((100, 100), dtype=bool)
            mask[40:60, 40:60] = True
            save_instances(cache / "instances.npz", [Instance(mask, "chair", 0.9)], (100, 100),
                           hashlib.sha256(photo.read_bytes()).hexdigest(), {"inference_confidence": 0.15})
            collection = root / "collection.json"
            collection.write_text(json.dumps({"images": [{"image": str(photo),
                                                          "depth_map": str(root / "missing.npy")}]}))
            reference = root / "reference.csv"
            with reference.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["image", "profile", "status", "candidate_area_fraction", "report"])
                writer.writeheader()
                for rule in ("metric", "objects", "hybrid"):
                    for distance in (2, 3):
                        writer.writerow({"image": str(photo), "profile": f"{rule}-{distance}m",
                                         "status": "sem_indicio_pela_regra", "candidate_area_fraction": 0,
                                         "report": "previous-report.json"})
            output = root / "output"
            args = ["--collection", str(collection), "--reference", str(reference),
                    "--instances-dir", str(root / "cache"), "--output", str(output)]
            with patch("mobility_risk.cli.estimate", side_effect=AssertionError("Sem profundidade")), \
                 patch("mobility_risk.cli.segment", side_effect=AssertionError("Sem nova segmentação")):
                main(args)
            with (output / "summary.csv").open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 7)
            self.assertEqual(rows[-1]["status"], "ocupacao_frontal_detectada")
            self.assertEqual(rows[-1]["result_kind"], "spatial_occupancy_only")
            self.assertEqual(list(output.rglob("*.npy")), [])
            with self.assertRaises(SystemExit):
                main(args)


if __name__ == "__main__":
    unittest.main()
