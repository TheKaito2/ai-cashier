# models/

| File | What | Licence |
|---|---|---|
| `mobilenet_v3_small.onnx` (+ `.data`) | the embedder the till runs; exported from torchvision by `tools/export_embedder.py` | BSD-3 (torchvision weights), Apache-2.0 (this repo) |
| `mobilenet_v3_large.onnx`, `resnet18.onnx` | reference backbones for experiment E3 | BSD-3 |
| `*-int8s.onnx` | static INT8 copies, `tools/export_embedder.py --int8-static` | as above |
| `chips_model.pt`, `drinks_model.pt` | the version-1 closed-set YOLOv8n detectors (6 + 6 classes) | **AGPL-3.0-derived** (Ultralytics). Research baseline only. Never loaded by the till or the server. |
