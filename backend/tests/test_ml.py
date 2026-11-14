import numpy as np
import torch
from app.ml.networks import UNetInpaint, SuperResolutionCNN
from app.ml.inference import inpaint_panorama, enhance_panorama


def test_unet_output_shape_and_range():
    m = UNetInpaint()
    with torch.no_grad():
        output=m(torch.rand(1,3,32,64),torch.zeros(1,1,32,64))
    assert output.shape==(1,3,32,64)
    assert 0<=output.min() and output.max()<=1


def test_sr_upscales_twice():
    m = SuperResolutionCNN()
    with torch.no_grad():
        output=m(torch.rand(1,3,32,64))
    assert output.shape==(1,3,64,128)


def test_inpaint_has_interpolation_fallback_without_weights():
    image = np.full((40,80,3),127,np.uint8)
    coverage = np.full((40,80),255,np.uint8)
    coverage[:, 20:45] = 0
    result, method=inpaint_panorama(image,coverage)
    assert result.shape==image.shape
    assert method in ('deterministic-fill','trained-unet')
    assert np.array_equal(result[coverage>0],image[coverage>0])
