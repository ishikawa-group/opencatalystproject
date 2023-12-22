from ocpmodels.trainers import ForcesTrainer
from ocpmodels.datasets import TrajectoryLmdbDataset
from ocpmodels import models
from ocpmodels.common import logger
from ocpmodels.common.utils import setup_logging
setup_logging()

import numpy as np
import copy
import os

#
# directories where lmdb file exists
#
#train_src = "../ocp/data/s2ef/train_100"
#val_src = "../ocp/data/s2ef/val_20"

train_src = "./data/dft/s2ef/train"
val_src   = "./data/dft/s2ef/val"

train_dataset = TrajectoryLmdbDataset({"src": train_src})

energies = []
for data in train_dataset:
    energies.append(data.y)

mean = np.mean(energies)
stdev = np.std(energies)

# Task
task = {
    "dataset": "trajectory_lmdb", # dataset used for the S2EF task
    "description": "Regressing to energies and forces for DFT trajectories from OCP",
    "type": "regression",
    "metric": "mae",
    "labels": ["potential energy"],
    "grad_input": "atomic forces",
    "train_on_free_atoms": True,
    "eval_on_free_atoms": True
}
# Model
model = {
    "name": "painn",
    "hidden_channels": 512,
    "num_layers": 6,
    "num_rbf": 128,
    "cutoff": 12.0,
    "max_neighbors": 50,
    "scale_file": "configs/s2ef/all/painn/painn_nb6_scaling_factors.pt",
    "regress_forces": True,
    "direct_forces": True,
    "use_pbc": True
}
# Optimizer
optimizer = {
    "batch_size": 1,         # originally 24
    "eval_batch_size": 1,    # originally 24
    "num_workers": 0,
    "load_balancing": "atoms",
    "optimizer": "AdamW",
    "optimizer_params": {"amsgrad": True},
    "lr_initial": 1.0e-4,
    "lr_gamma": 0.8,
    "scheduler": "ReduceLROnPlateau",
    "mode": "min",
    "factor": 0.8,
    "patience": 3,
    "max_epochs": 1,         # used for demonstration purposes
    "force_coefficient": 100,
    "energy_coefficient": 1,
    "ema_decay": 0.999,
    "clip_grad_norm": 10,
    "loss_energy": "mae",
    "loss_force": "l2mae",
    "weight_decay": 0
}

# Dataset
dataset = [
    {"src": train_src,
        "normalize_labels": True,
        "target_mean": mean,
        "target_std": stdev,
        "grad_target_mean": 0.0,
        "grad_target_std": stdev
    }, # train set 
    {"src": val_src}, # val set (optional)
]

trainer = ForcesTrainer(
    task        = task,
    model       = copy.deepcopy(model), # copied for later use, not necessary in practice.
    dataset     = dataset,
    optimizer   = optimizer,
    identifier  = "S2EF-PAINN",
    run_dir     = "./", # directory to save results if is_debug=False. Prediction files are saved here so be careful not to override!
    is_debug    = False, # if True, do not save checkpoint, logs, or results
    print_every = 5,
    seed        = 0, # random seed to use
    logger      = "tensorboard", # logger of choice (tensorboard and wandb supported)
    local_rank  = 0,
    amp         = True, # use PyTorch Automatic Mixed Precision (faster training and less memory usage),
)

trainer.train()

# The `best_checpoint.pt` file contains the checkpoint with the best val performance
checkpoint_path = os.path.join(trainer.config["cmd"]["checkpoint_dir"], "best_checkpoint.pt")

# Append the dataset with the test set. We use the same val set for demonstration.

# Dataset
dataset.append(
  {'src': val_src}, # test set (optional)
)
dataset

pretrained_trainer = ForcesTrainer(
    task        = task,
    model       = model,
    dataset     = dataset,
    optimizer   = optimizer,
    identifier  = "S2EF-val-example",
    run_dir     = "./", # directory to save results if is_debug=False. Prediction files are saved here so be careful not to override!
    is_debug    = False, # if True, do not save checkpoint, logs, or results
    print_every = 10,
    seed        = 0, # random seed to use
    logger      = "tensorboard", # logger of choice (tensorboard and wandb supported)
    local_rank  = 0,
    amp         = True, # use PyTorch Automatic Mixed Precision (faster training and less memory usage)
)

pretrained_trainer.load_checkpoint(checkpoint_path=checkpoint_path)

# make predictions on the existing test_loader
predictions = pretrained_trainer.predict(pretrained_trainer.test_loader, results_file="s2ef_results", disable_tqdm=False)

energies = predictions["energy"]
forces = predictions["forces"]

