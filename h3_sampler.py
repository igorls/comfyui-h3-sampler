"""Sampler for MiniMax H3 Image: plain Euler on the distilled grid for structure, a second-order
exponential step with fresh noise and a small noise-level underestimate for texture.

Why:
- H3 Image is step-distilled: one output head per interval of a fixed noise grid
  (1, .9675, .8875, .75, .5328, .232, 0). Each model call picks its head from the noise level it is
  given and the next level of the schedule (comfy/ldm/minimax/model.py, `forward`).
- Structure (composition, objects, identity) is set above ~0.5. Plain Euler on the grid is what the
  heads were distilled for and keeps object structure cleanest; second-order steps or fresh noise
  there duplicated objects and cost likeness in tests.
- Texture (skin, hair, fabric, grain) is drawn below ~0.5. There a second-order exponential step
  (exponential Heun), ancestral noise, and telling the second evaluation a slightly lower noise level
  give photographic micro-detail.

Every model call is told its exact step (`sample_sigmas` = [level, target level]) so H3 uses the right
distilled head. With texture off (texture_from 0) the result is pixel-identical to ComfyUI's
sample_euler on the same sigmas.
"""
from __future__ import annotations

import math

import torch
from tqdm.auto import trange

from comfy.k_diffusion.sampling import default_noise_sampler, to_d


def _with_step(extra_args: dict, told, target) -> dict:
    """extra_args whose transformer_options tell H3 which step this call belongs to."""
    model_options = dict(extra_args.get("model_options", {}))
    transformer_options = dict(model_options.get("transformer_options", {}))
    transformer_options["sample_sigmas"] = torch.stack([torch.as_tensor(told, dtype=torch.float32).cpu(),
                                                        torch.as_tensor(target, dtype=torch.float32).cpu()])
    model_options["transformer_options"] = transformer_options
    return {**extra_args, "model_options": model_options}


def _phi(h: float) -> tuple[float, float]:
    """phi_1 and phi_2 of the exponential integrator at step size h (in -log sigma)."""
    if h < 1e-4:
        return 1.0 - h / 2.0, 0.5 - h / 6.0
    e = math.exp(-h)
    return (1.0 - e) / h, (h - 1.0 + e) / (h * h)


def step_plan(sigmas: list[float], texture_from: float, sigma_min: float) -> list[tuple]:
    """(from, to, is_texture, index of the original step). Structure steps are kept as given. Steps that
    start at or below texture_from are texture steps; one that ends at 0 ends at sigma_min instead, so its
    second evaluation has a level to sit at, and the final move to 0 needs no model call."""
    plan = []
    for k, (a, b) in enumerate(zip(sigmas[:-1], sigmas[1:])):
        if a > texture_from + 1e-6:
            plan.append((a, b, False, k))
        else:
            plan.append((a, sigma_min if b <= 0.0 else b, True, k))
    return plan


@torch.no_grad()
def sample_h3(model, x, sigmas, extra_args=None, callback=None, disable=None,
              texture_from: float = 0.55, eta: float = 0.65, detail: float = 0.07):
    """KSAMPLER function. sigmas: H3's grid (or ComfyUI's simple scheduler at 6 steps, the same within ~0.001)."""
    extra_args = {} if extra_args is None else extra_args
    noise_sampler = default_noise_sampler(x, seed=extra_args.get("seed", None))
    s_in = x.new_ones([x.shape[0]])
    sigma_min = float(model.inner_model.inner_model.model_sampling.sigma_min)
    plan = step_plan([float(s) for s in sigmas], texture_from, sigma_min)
    denoised_last = None
    for i in trange(len(plan), disable=disable):
        a, b, texture, k = plan[i]
        if not texture:
            # Euler, op for op as ComfyUI's sample_euler (same tensors), on the distilled grid.
            sigma, sigma_next = sigmas[k], sigmas[k + 1]
            denoised = model(x, sigma * s_in, **_with_step(extra_args, sigma, sigma_next))
            if callback is not None:
                callback({"x": x, "i": i, "sigma": sigma, "sigma_hat": sigma, "denoised": denoised})
            x = x + to_d(x, sigma, denoised) * (sigma_next - sigma)
            denoised_last = denoised
            continue
        # Texture: exponential Heun in t = -log sigma (data prediction, flow model).
        after = plan[i + 1][1] if i + 1 < len(plan) else 0.0
        d1 = model(x, a * s_in, **_with_step(extra_args, a, b))
        if callback is not None:
            callback({"x": x, "i": i, "sigma": sigmas[k], "sigma_hat": sigmas[k], "denoised": d1})
        r = b / a
        x2 = r * x + (1.0 - r) * d1
        told = b * (1.0 - detail)                       # detail: the second evaluation is told a lower level
        d2 = model(x2, told * s_in, **_with_step(extra_args, told, after))
        p1, p2 = _phi(math.log(a / b))
        d_bar = ((p1 - p2) * d1 + p2 * d2) / p1           # the step's denoised estimate (a convex blend)
        eps = (x - (1.0 - a) * d_bar) / a                 # its noise estimate at the start level
        if eta > 0.0:
            eps = math.sqrt(max(0.0, 1.0 - eta * eta)) * eps + eta * noise_sampler(a, b)
        x = (1.0 - b) * d_bar + b * eps
        denoised_last = d_bar
    if float(sigmas[-1]) <= 0.0 and plan and plan[-1][2]:
        x = denoised_last                                # the final move from sigma_min to 0, no call
    return x
