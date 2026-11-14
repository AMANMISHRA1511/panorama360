import torch
from torch import nn
import torch.nn.functional as F

class ConvBlock(nn.Module):
    def __init__(self, inc, outc):
        super().__init__()
        self.layers = nn.Sequential(nn.Conv2d(inc, outc, 3, padding=1), nn.ReLU(inplace=True),
                                    nn.Conv2d(outc, outc, 3, padding=1), nn.ReLU(inplace=True))
    def forward(self, x):
        return self.layers(x)

class UNetInpaint(nn.Module):
    """Four-channel image + hole-mask U-Net predicts missing RGB pixels."""
    def __init__(self):
        super().__init__()
        self.down1 = ConvBlock(4, 32)
        self.down2 = ConvBlock(32, 64)
        self.bottleneck = ConvBlock(64, 128)
        self.up2 = ConvBlock(192, 64)
        self.up1 = ConvBlock(96, 32)
        self.out = nn.Conv2d(32, 3, 1)
    def forward(self, image, mask):
        x1 = self.down1(torch.cat([image, mask], dim=1))
        x2 = self.down2(F.avg_pool2d(x1, 2))
        x3 = self.bottleneck(F.avg_pool2d(x2, 2))
        d2 = self.up2(torch.cat([F.interpolate(x3, size=x2.shape[-2:], mode="bilinear", align_corners=False), x2], dim=1))
        d1 = self.up1(torch.cat([F.interpolate(d2, size=x1.shape[-2:], mode="bilinear", align_corners=False), x1], dim=1))
        return torch.sigmoid(self.out(d1))

class SuperResolutionCNN(nn.Module):
    """2x super-resolution: 3 conv blocks + PixelShuffle(2)."""
    def __init__(self):
        super().__init__()
        self.layers = nn.Sequential(nn.Conv2d(3, 48, 5, padding=2), nn.ReLU(inplace=True),
                                    nn.Conv2d(48, 48, 3, padding=1), nn.ReLU(inplace=True),
                                    nn.Conv2d(48, 12, 3, padding=1), nn.PixelShuffle(2))
    def forward(self, image):
        base = F.interpolate(image, scale_factor=2, mode="bilinear", align_corners=False)
        return (base + self.layers(image)).clamp(0, 1)
