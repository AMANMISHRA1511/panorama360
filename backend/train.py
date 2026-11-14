"""Train example U-Net/SR networks on your own 2:1 panoramas (JPG/PNG).
Run: python train.py --data ./training-images --epochs 4 --batch-size 2
This starts random weights and is a *demo training pipeline*, not a pretrained model.
For useful hole completion you need a diverse dataset and substantial training.
"""
import argparse
import random
from pathlib import Path
import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from app.config import WEIGHTS_DIR
from app.ml.networks import UNetInpaint, SuperResolutionCNN

class PanoramaDataset(Dataset):
    def __init__(self, directory):
        self.files = [f for f in Path(directory).rglob("*") if f.suffix.lower() in (".jpg", ".jpeg", ".png")]
        if not self.files:
            raise ValueError("No JPG/PNG training photos found")
    def __len__(self):
        return len(self.files)
    def __getitem__(self, idx):
        image = cv2.imread(str(self.files[idx]))
        if image is None:
            raise ValueError(f"Cannot decode {self.files[idx]}")
        image = cv2.resize(image, (256, 128))
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB).astype(np.float32) / 255
        mask = np.zeros((128, 256), np.float32)
        for _ in range(random.randint(1, 4)):
            x, y = random.randrange(256), random.randrange(128)
            mask[y:min(128, y + random.randrange(16, 65)), x:min(256, x + random.randrange(16, 96))] = 1
        image = torch.from_numpy(image.transpose(2, 0, 1).copy())
        holes = torch.from_numpy(mask[None])
        return image, holes

def train(data, epochs, batch_size, lr):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    loader = DataLoader(PanoramaDataset(data), batch_size=batch_size, shuffle=True, num_workers=0)
    net_inpaint = UNetInpaint().to(device)
    net_sr = SuperResolutionCNN().to(device)
    optim_inpaint = torch.optim.Adam(net_inpaint.parameters(), lr=lr)
    optim_sr = torch.optim.Adam(net_sr.parameters(), lr=lr)
    for epoch in range(epochs):
        running = 0
        for rgb, holes in loader:
            rgb, holes = rgb.to(device), holes.to(device)
            optim_inpaint.zero_grad()
            prediction = net_inpaint(rgb * (1 - holes), holes)
            loss = (torch.abs(prediction - rgb) * (1 + 4 * holes)).mean()
            loss.backward()
            optim_inpaint.step()
            optim_sr.zero_grad()
            low = F.interpolate(rgb, scale_factor=.5, mode="bilinear", align_corners=False)
            upscaled = net_sr(low)
            sr_loss = F.l1_loss(upscaled, rgb)
            sr_loss.backward()
            optim_sr.step()
            running += loss.item() + sr_loss.item()
        print(f"Epoch {epoch+1}/{epochs}: mean combined loss {running/len(loader):.4f} ({device})")
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(net_inpaint.cpu().state_dict(), WEIGHTS_DIR / "inpaint.pt")
    torch.save(net_sr.cpu().state_dict(), WEIGHTS_DIR / "superres.pt")
    print(f"Saved weights to {WEIGHTS_DIR}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Folder containing training panorama images")
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--lr", type=float, default=0.0002)
    args = parser.parse_args()
    train(args.data, args.epochs, args.batch_size, args.lr)
