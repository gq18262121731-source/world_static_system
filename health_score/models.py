"""Independent sequence reconstruction models; never imports the live backend."""
from __future__ import annotations

import copy
import random
import time

import numpy as np
import torch
from torch import nn


class SequenceAutoencoder(nn.Module):
    """Both variants reconstruct (batch, time, feature), without batch mixing."""

    def __init__(self, features=4, hidden_size=48, latent_size=12, variational=True):
        super().__init__()
        self.variational = variational
        self.encoder = nn.LSTM(features, hidden_size, batch_first=True)
        self.mu_head = nn.Linear(hidden_size, latent_size)
        self.logvar_head = nn.Linear(hidden_size, latent_size)
        self.decoder_seed = nn.Linear(latent_size, hidden_size)
        self.decoder = nn.LSTM(hidden_size, hidden_size, batch_first=True)
        self.output = nn.Linear(hidden_size, features)

    def forward(self, values):
        if values.ndim != 3:
            raise ValueError("Expected (batch, time, feature) input")
        _, (hidden, _) = self.encoder(values)
        mu = self.mu_head(hidden[-1])
        logvar = self.logvar_head(hidden[-1]).clamp(-10, 8)
        latent = mu
        if self.variational and self.training:
            latent = mu + torch.exp(0.5 * logvar) * torch.randn_like(mu)
        seed = self.decoder_seed(latent).unsqueeze(1).repeat(1, values.shape[1], 1)
        decoded, _ = self.decoder(seed)
        return self.output(decoded), mu, logvar


def seed_everything(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(2)


def reconstruction_scores(model, values, device, batch_size=256):
    model.eval()
    chunks = []
    with torch.no_grad():
        for start in range(0, len(values), batch_size):
            batch = torch.as_tensor(values[start:start + batch_size], device=device)
            reconstructed, _, _ = model(batch)
            if reconstructed.shape != batch.shape:
                raise RuntimeError("Reconstruction shape must exactly match input")
            chunks.append(((batch - reconstructed) ** 2).mean(dim=(1, 2)).cpu().numpy())
    return np.concatenate(chunks).astype(np.float64)


def fit_sequence_model(train, normal_validation, config, seed, variational, device, progress=None):
    seed_everything(seed)
    started = time.perf_counter()
    model = SequenceAutoencoder(
        hidden_size=config['hidden_size'], latent_size=config['latent_size'],
        variational=variational,
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config['learning_rate'])
    training_tensor = torch.as_tensor(train, device=device)
    best_state, best_loss, best_epoch, stale = None, float('inf'), 0, 0
    history = []
    for epoch in range(1, config['epochs'] + 1):
        model.train()
        order = torch.randperm(len(train), device=device)
        sums = np.zeros(3, dtype=np.float64)
        beta = config['kl_beta'] * min(1.0, epoch / config['kl_warmup_epochs']) if variational else 0.0
        for start in range(0, len(order), config['batch_size']):
            batch = training_tensor[order[start:start + config['batch_size']]]
            optimizer.zero_grad(set_to_none=True)
            reconstruction, mu, logvar = model(batch)
            mse = ((batch - reconstruction) ** 2).mean()
            kl = -0.5 * (1 + logvar - mu.square() - logvar.exp()).mean()
            loss = mse + beta * kl
            if not torch.isfinite(loss):
                raise RuntimeError('Non-finite training loss')
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            sums += np.array([loss.item(), mse.item(), kl.item()]) * len(batch)
        validation_loss = float(reconstruction_scores(model, normal_validation, device).mean())
        row = dict(zip(('loss', 'reconstruction', 'kl'), (sums / len(train)).tolist()))
        row.update(epoch=epoch, beta=beta, validation_reconstruction=validation_loss)
        history.append(row)
        if validation_loss < best_loss - 1e-5:
            best_loss, best_epoch, stale = validation_loss, epoch, 0
            best_state = copy.deepcopy(model.state_dict())
        else:
            stale += 1
        if progress and (epoch == 1 or epoch % 10 == 0):
            progress(f"epoch {epoch:02d}: normal-validation MSE={validation_loss:.4f}")
        if stale >= config['patience']:
            break
    model.load_state_dict(best_state)
    model.eval()
    elapsed = time.perf_counter() - started
    return model, {
        'fit_seconds': elapsed, 'best_epoch': best_epoch,
        'epochs_run': len(history), 'best_normal_validation_mse': best_loss,
        'parameter_count': sum(p.numel() for p in model.parameters()),
        'inference': 'posterior mean; deterministic; no sampling',
        'history': history,
    }
