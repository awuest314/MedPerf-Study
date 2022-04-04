# Hello World Script
#
# This script is unrelated to the MLCube interface. It could be run
# independently without issues. It provides the actual implementation
# of the app.
import os
import csv
import argparse
import matplotlib.pyplot as plt

from PIL import Image
import numpy as np
import nibabel as nib

# !pip install -q torch_snippets pytorch_model_summary
# from torchvision import transforms
# from sklearn.model_selection import train_test_split
from torch.utils.data import Dataset, DataLoader
import torch
import torch.nn as nn

import torch.nn.functional as F
from torchvision.models import vgg16_bn
import time
from typing import List

import UNet
from UNet import dice_coef_multilabel, dice_coef

# Define PyTorch Dataloader
class CTScanDataset(Dataset):
    """
    KAGGLE dataset.
    Accredit to https://pytorch.org/tutorials/beginner/data_loading_tutorial.html
    """

    def __init__(self, data_dir, transform=None):
        """
        Args:
            data_dir: data folder directory
            transform (callable, optional): Optional transform to be applied
                on a sample.
        """
        self.root_dir = data_dir
        self.files = os.listdir(data_dir)
        self.transform = transform

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):
        if torch.is_tensor(idx):
            idx = idx.tolist()
        
        # file_path = os.path.join(self.root_dir, self.files[idx])

        with open(os.path.join(self.root_dir, self.files[idx]), 'rb') as f:
            data = np.load(f)
            feature = data[:-1, :, :].astype('float32')
            label = data[-1, :, :].astype('int8')

        if self.transform:
            sample = self.transform(sample)

        return feature, label
    

def unet_model(images, model_path):
    """
    Generates predictions for images
    
    Args:
        images: images to be predicted
        model_path: path to PyTorch model"""
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    test_dataset = images
    # define test loader
    test_loader = DataLoader(test_dataset, batch_size=8, shuffle=False, num_workers=0)
    # load pre-trained torch model 
    #net = torch.load(model_path, map_location=torch.device(device))
    net = UNet.UNet()
    net.load_state_dict(torch.load(model_path, map_location=torch.device(device)))
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(50))
    optimizer = torch.optim.SGD(net.parameters(), lr=0.01, momentum=0.9, weight_decay=0.0001)
    # load dataset
    test_dataset = CTScanDataset(images)
    #define test_loader
    testloader = DataLoader(test_dataset, batch_size=8,
                             shuffle=False, num_workers=0)

    loss = 0
    dice_total_avg = 0
    dice_class0_avg = 0
    dice_class1_avg = 0
    with torch.no_grad():
        for data in testloader:
            images, targets = data
            images, targets = images.to(device=device, dtype=torch.float), targets.to(device=device)
            targets = F.one_hot(targets.long(), num_classes=2)
            targets = torch.permute(targets, (0, 3, 1, 2))
            outputs = net(images)

            loss += criterion(outputs, targets.float()).item()

            outputs_cat = F.one_hot(torch.argmax(outputs, axis=1), num_classes=2)
            outputs_cat = torch.permute(outputs_cat, (0, 3, 1, 2))

            dice_avg, dice_class = dice_coef_multilabel(targets, outputs_cat, numLabels=2)
            dice_total_avg += dice_avg.item()
            dice_class0_avg += dice_class[0].item()
            dice_class1_avg += dice_class[1].item()
    
    dice_total_avg /= len(testloader)
    dice_class0_avg /= len(testloader)
    dice_class1_avg /= len(testloader)

    return loss, dice_total_avg, dice_class0_avg, dice_class1_avg


if __name__ == '__main__':
    print("App")
    parser = argparse.ArgumentParser("MedPerf DFCI Example")
    parser.add_argument('--names', dest="names", type=str, help="directory containing names")
    parser.add_argument('--out', dest="out", type=str, help="path to store resulting predictions")

    parser.add_argument('--model_info', dest="model_info", type=str, help="directory containing model info")

    #parser.add_argument('--data_p', dest="data", type=str, help="directory containing images")

    args = parser.parse_args()
    print(args.out)
    print(args.model_info)
    print(args.names)
    print("run unet model")
  
    loss, dice_total_avg, dice_class0_avg, dice_class1_avg = unet_model(args.names, args.model_info)
    list_vals = [loss, dice_total_avg, dice_class0_avg, dice_class1_avg]

    out_file = os.path.join(args.out, "predictions.csv")
    with open(out_file, "w") as f:
        writer = csv.writer(f)
        writer.writerow(["loss", "dice_total_avg", "dice_class0_avg","dice_class1_avg"])
        for idx in range(0,4):
            writer.writerow([idx, list_vals[idx]])
            