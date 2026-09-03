"""The public-benchmark layout: enrolment views from train, probes from test."""
import csv
from pathlib import Path

import cv2
import numpy as np

from research.dataset import ImageFolderSource
from research.prepare_grocerystore import prepare


def _fake_dataset(root: Path, n_train=7, n_test=11) -> Path:
    """Three classes, two of them cartons, laid out like the real repo."""
    ds = root / "dataset"
    specs = [("Packages", "Milk", "Arla-Standard-Milk", 0, 0),
             ("Packages", "Juice", "Bravo-Apple-Juice", 1, 1),
             ("Fruit", "Apple", "Granny-Smith", 2, 2)]
    lines = {"train.txt": [], "test.txt": []}
    for group, coarse, fine, fid, cid in specs:
        for split, n in (("train", n_train), ("test", n_test)):
            for i in range(1, n + 1):
                rel = f"{split}/{group}/{coarse}/{fine}/{fine}_{i:03d}.jpg"
                p = ds / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(p), np.full((32, 32, 3), 40 + i, np.uint8))
                lines[f"{split}.txt"].append(f"{rel}, {fid}, {cid}")
        icon = ds / "iconic-images-and-descriptions" / group / coarse / fine / f"{fine}_Iconic.jpg"
        icon.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(icon), np.full((32, 32, 3), 200, np.uint8))
    for name, ls in lines.items():
        (ds / name).write_text("\n".join(ls) + "\n")
    with (ds / "classes.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Class Name (str)", "Class ID (int)", "Coarse Class Name (str)",
                    "Coarse Class ID (int)", "Iconic Image Path (str)", "Product Description Path (str)"])
        for group, coarse, fine, fid, cid in specs:
            w.writerow([fine, fid, coarse, cid,
                        f"/iconic-images-and-descriptions/{group}/{coarse}/{fine}/{fine}_Iconic.jpg",
                        f"/iconic-images-and-descriptions/{group}/{coarse}/{fine}/{fine}_Description.txt"])
    return ds


def test_three_roots_with_train_views_before_test_probes(tmp_path):
    ds = _fake_dataset(tmp_path)
    counts = prepare(ds, tmp_path / "public")

    assert counts == {"grocerystore-packages": 2, "grocerystore-all": 3, "grocerystore-iconic": 3}
    milk = tmp_path / "public" / "grocerystore-all" / "Arla-Standard-Milk"
    names = sorted(p.name for p in milk.iterdir())
    assert names[:5] == [f"a-train-{i:03d}.jpg" for i in range(1, 6)]
    assert names[5:] == [f"b-test-{i:03d}.jpg" for i in range(1, 10)]
    assert all(p.is_symlink() for p in milk.iterdir())

    src = ImageFolderSource(tmp_path / "public" / "grocerystore-packages")
    assert [s.sku_id for s in src.skus()] == ["Arla-Standard-Milk", "Bravo-Apple-Juice"]
    assert src.skus()[0].name == "Arla Standard Milk"
    frames = src.frames("Arla-Standard-Milk")
    assert len(frames) == 14
    # the pixel value encodes which photograph each view came from: train 1..5 then test 1..9
    assert [int(f[0, 0, 0]) - 40 for f in frames] == [1, 2, 3, 4, 5, 1, 2, 3, 4, 5, 6, 7, 8, 9]


def test_iconic_root_puts_the_pack_shot_first(tmp_path):
    ds = _fake_dataset(tmp_path)
    prepare(ds, tmp_path / "public")
    src = ImageFolderSource(tmp_path / "public" / "grocerystore-iconic")
    frames = src.frames("Granny-Smith")
    assert len(frames) == 14                      # the cap: iconic + 4 train + 9 test
    assert int(frames[0][0, 0, 0]) == 200          # view 000 is the manufacturer image
