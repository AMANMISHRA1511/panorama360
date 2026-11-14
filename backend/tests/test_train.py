from pathlib import Path
import cv2
import numpy as np
import torch
import train as training
from app.ml.networks import UNetInpaint, SuperResolutionCNN


def test_training_script_saves_loadable_checkpoints(tmp_path, monkeypatch):
    examples = tmp_path / 'examples'
    weights = tmp_path / 'weights'
    examples.mkdir()
    test_image = np.random.default_rng(2).integers(0, 255, size=(64,128,3), dtype=np.uint8)
    cv2.imwrite(str(examples/'photo.png'), test_image)
    monkeypatch.setattr(training,'WEIGHTS_DIR',weights)
    training.train(examples, epochs=1, batch_size=1, lr=.0002)
    assert (weights / 'inpaint.pt').is_file()
    assert (weights / 'superres.pt').is_file()
    UNetInpaint().load_state_dict(torch.load(weights/'inpaint.pt',map_location='cpu',weights_only=True))
    SuperResolutionCNN().load_state_dict(torch.load(weights/'superres.pt',map_location='cpu',weights_only=True))
