"""Samplers for MiniMax H3 Image, tuned for photographic realism.

Three tested recipes on H3 Image's 6-step distilled PDD noise grid (1, .9675, .8875, .75, .5328, .232, 0):

1. ``spectral 6 (fast, highest likeness)`` (6 model calls, plan EEFFFE):
   - Steps 0-1: plain Euler on the distilled grid sets global layout and pose.
   - Steps 2-4: variance-preserving 2D FFT frequency-split re-noising. Low spatial frequencies stay
     deterministically locked to Euler (preserving face proportions, hands, props and text), while high
     spatial frequencies draw fresh noise with exact unit white-noise marginal distribution N(0, I).
   - Step 5: plain Euler finishes cleanly.
   Beat v1.1 on face-match likeness across edits while running 25-45% faster (6 calls instead of 8).

2. ``spectral + texture 8 (richest detail)`` (8 model calls, plan EEFFHH):
   - Steps 0-1: plain Euler.
   - Steps 2-3: frequency-split spectral re-noising.
   - Steps 4-5: 2nd-order exponential Heun with frequency-split fresh noise and a small noise-level
     underestimate (``detail``) for the sharpest skin pores, beard/hair strands and fabric weave.

3. ``texture 8 (v1.1 classic)`` (8 model calls):
   - Plain Euler above ``texture_from``, then 2nd-order exponential Heun with isotropic ancestral noise
     and ``detail`` below ``texture_from``. With ``texture_from = 0`` (or ``eta = 0`` in spectral 6) the
     result is pixel-identical to ComfyUI's ``sample_euler`` on the same sigmas.

Every model call is told its exact step (``sample_sigmas = [told, target]``) so H3 always picks the
intended distilled head. Runs that start mid-schedule (a second pass or img2img refine) automatically
align to the matching step of the 6-step plan.
"""
from __future__ import annotations

import math

import torch
from tqdm.auto import trange

from comfy.k_diffusion.sampling import default_noise_sampler, to_d

MODES = [
    "spectral 6 (fast, highest likeness)",
    "spectral + texture 8 (richest detail)",
    "texture 8 (v1.1 classic)",
]

MODE_PLANS = {
    MODES[0]: "EEFFFE",
    MODES[1]: "EEFFHH",
}

OFFICIAL_SIGMAS = (
    1.0,
    0.9675236940383911,
    0.8875485062599182,
    0.75,
    0.5327739119529724,
    0.23200887441635132,
    0.0,
)


def _with_step(extra_args: dict, told, target) -> dict:
    """extra_args whose transformer_options tell H3 which distilled head interval this call belongs to."""
    model_options = dict(extra_args.get("model_options", {}))
    transformer_options = dict(model_options.get("transformer_options", {}))
    transformer_options["sample_sigmas"] = torch.stack([
        torch.as_tensor(told, dtype=torch.float32).cpu(),
        torch.as_tensor(target, dtype=torch.float32).cpu(),
    ])
    model_options["transformer_options"] = transformer_options
    return {**extra_args, "model_options": model_options}


def _phi(h: float) -> tuple[float, float]:
    """phi_1 and phi_2 of the exponential integrator at step size h (in -log sigma)."""
    if h < 1e-4:
        return 1.0 - h / 2.0, 0.5 - h / 6.0
    e = math.exp(-h)
    return (1.0 - e) / h, (h - 1.0 + e) / (h * h)


def _radial_freq_grid(h: int, w: int, device) -> torch.Tensor:
    """Normalized radial spatial frequency in [0, 1] for 2D rfft2 over (H, W)."""
    fy = torch.fft.fftfreq(h, device=device, dtype=torch.float32)[:, None] * 2.0
    fx = torch.fft.rfftfreq(w, device=device, dtype=torch.float32)[None, :] * 2.0
    return torch.sqrt((fy * fy + fx * fx) * 0.5).clamp(0.0, 1.0)


def _highpass_weight(r: torch.Tensor, cutoff: float, width: float) -> torch.Tensor:
    """Smooth raised-cosine transition: 0 for r <= cutoff, 1 for r >= cutoff + width."""
    t = ((r - cutoff) / max(width, 1e-4)).clamp(0.0, 1.0)
    return 0.5 - 0.5 * torch.cos(math.pi * t)


def spectral_mix_noise(
    eps_old: torch.Tensor,
    eps_new: torch.Tensor,
    eta_low: float = 0.0,
    eta_high: float = 0.85,
    cutoff: float = 0.25,
    width: float = 0.20,
    hf_scale: float = 1.0,
) -> torch.Tensor:
    """Variance-preserving frequency-split noise mix in the 2D FFT domain.

    For two independent unit white Gaussian fields ``eps_old`` and ``eps_new``, mixing each Fourier bin
    with ``sqrt(1 - eta(r)^2) * E_old + eta(r) * E_new`` preserves an exact N(0, I) white spectrum
    (when ``hf_scale == 1.0``), keeping low-frequency structure locked to ``eps_old`` while replacing
    high-frequency noise with ``eps_new``.
    """
    if eta_low <= 0.0 and eta_high <= 0.0 and abs(hf_scale - 1.0) <= 1e-6:
        return eps_old
    if eta_low >= 1.0 and eta_high >= 1.0 and abs(hf_scale - 1.0) <= 1e-6:
        return eps_new
    h, w = eps_old.shape[-2], eps_old.shape[-1]
    r = _radial_freq_grid(h, w, eps_old.device)
    hp = _highpass_weight(r, cutoff, width)
    eta_f = eta_low + (eta_high - eta_low) * hp
    s_f = 1.0 + (hf_scale - 1.0) * hp
    keep_f = torch.sqrt((1.0 - eta_f * eta_f).clamp_min(0.0))

    e_old = torch.fft.rfft2(eps_old.float(), norm="ortho")
    e_new = torch.fft.rfft2(eps_new.float(), norm="ortho")
    e_mix = s_f * (keep_f * e_old + eta_f * e_new)
    return torch.fft.irfft2(e_mix, s=(h, w), norm="ortho").to(eps_old.dtype)


def _model_grid(model) -> tuple[float, ...]:
    ms = getattr(getattr(model, "inner_model", None), "inner_model", None)
    ms = getattr(ms, "model_sampling", None)
    grid = getattr(ms, "grid", None)
    if grid is not None:
        return tuple(float(s) for s in grid.flip(0).tolist())
    return OFFICIAL_SIGMAS


def _sigma_min(model) -> float:
    ms = getattr(getattr(model, "inner_model", None), "inner_model", None)
    ms = getattr(ms, "model_sampling", None)
    if ms is not None and hasattr(ms, "sigma_min"):
        return float(ms.sigma_min)
    return 1e-4


def plan_for_sigmas(plan_str: str, sigmas: list[float], grid: tuple[float, ...] = OFFICIAL_SIGMAS) -> list[str]:
    """Align a 6-step plan to ``sigmas``; a second pass starting later in the grid takes the matching tail."""
    n = max(0, len(sigmas) - 1)
    if n == 0:
        return []
    steps = [s for s in grid if s > 0.0]
    s0 = float(sigmas[0])
    start = 0
    if steps:
        k = min(range(len(steps)), key=lambda j: abs(steps[j] - s0))
        if abs(steps[k] - s0) < 0.02 and k + n <= len(plan_str):
            start = k
    codes = list(plan_str[start:start + n])
    while len(codes) < n:
        codes.append("E")
    return codes


def classic_step_plan(sigmas: list[float], texture_from: float, sigma_min: float) -> list[tuple]:
    """(from, to, is_texture, step_index) for the v1.1 classic Euler + Exp-Heun recipe."""
    plan = []
    for k, (a, b) in enumerate(zip(sigmas[:-1], sigmas[1:])):
        if a > texture_from + 1e-6:
            plan.append((a, b, False, k))
        else:
            plan.append((a, sigma_min if b <= 0.0 else b, True, k))
    return plan


@torch.no_grad()
def _sample_classic(model, x, sigmas, extra_args, callback, disable,
                    texture_from: float, eta: float, detail: float):
    noise_sampler = default_noise_sampler(x, seed=extra_args.get("seed", None))
    s_in = x.new_ones([x.shape[0]])
    sigma_min = _sigma_min(model)
    plan = classic_step_plan([float(s) for s in sigmas], texture_from, sigma_min)
    denoised_last = None
    for i in trange(len(plan), disable=disable):
        a, b, texture, k = plan[i]
        if not texture:
            sigma, sigma_next = sigmas[k], sigmas[k + 1]
            denoised = model(x, sigma * s_in, **_with_step(extra_args, sigma, sigma_next))
            if callback is not None:
                callback({"x": x, "i": i, "sigma": sigma, "sigma_hat": sigma, "denoised": denoised})
            x = x + to_d(x, sigma, denoised) * (sigma_next - sigma)
            denoised_last = denoised
            continue
        after = plan[i + 1][1] if i + 1 < len(plan) else 0.0
        d1 = model(x, a * s_in, **_with_step(extra_args, a, b))
        if callback is not None:
            callback({"x": x, "i": i, "sigma": sigmas[k], "sigma_hat": sigmas[k], "denoised": d1})
        r = b / a
        x2 = r * x + (1.0 - r) * d1
        told = b * (1.0 - detail)
        d2 = model(x2, told * s_in, **_with_step(extra_args, told, after))
        p1, p2 = _phi(math.log(a / b))
        d_bar = ((p1 - p2) * d1 + p2 * d2) / p1
        eps = (x - (1.0 - a) * d_bar) / a
        if eta > 0.0:
            eps = math.sqrt(max(0.0, 1.0 - eta * eta)) * eps + eta * noise_sampler(a, b)
        x = (1.0 - b) * d_bar + b * eps
        denoised_last = d_bar
    if float(sigmas[-1]) <= 0.0 and plan and plan[-1][2]:
        x = denoised_last
    return x


@torch.no_grad()
def sample_h3_realism(
    model,
    x,
    sigmas,
    extra_args=None,
    callback=None,
    disable=None,
    mode: str = MODES[0],
    eta: float = 0.85,
    spectral_cutoff: float = 0.25,
    hf_scale: float = 1.0,
    detail: float = 0.07,
    texture_from: float = 0.55,
):
    """KSAMPLER function for MiniMax H3 Image."""
    extra_args = {} if extra_args is None else extra_args
    if mode == MODES[2] or mode.startswith("texture 8"):
        return _sample_classic(model, x, sigmas, extra_args, callback, disable,
                               texture_from=texture_from, eta=eta, detail=detail)

    plan_str = MODE_PLANS.get(mode, MODE_PLANS[MODES[0]])
    sig_list = [float(s) for s in sigmas]
    codes = plan_for_sigmas(plan_str, sig_list, grid=_model_grid(model))
    n = len(codes)

    noise_sampler = default_noise_sampler(x, seed=extra_args.get("seed", None))
    s_in = x.new_ones([x.shape[0]])
    sigma_min = _sigma_min(model)

    # In the 8-step hybrid, late Exp-Heun uses the tested 0.65/0.85 ratio relative to mid spectral eta
    late_eta = min(1.0, eta * (0.65 / 0.85))
    late_cutoff = max(0.0, spectral_cutoff - 0.10)
    denoised_last = None
    ended_with_heun = False

    for k in trange(n, disable=disable):
        a, b = sig_list[k], sig_list[k + 1]
        code = codes[k]

        if code == "E":
            sigma, sigma_next = sigmas[k], sigmas[k + 1]
            d = model(x, sigma * s_in, **_with_step(extra_args, sigma, sigma_next))
            if callback is not None:
                callback({"x": x, "i": k, "sigma": sigma, "sigma_hat": sigma, "denoised": d})
            x = x + to_d(x, sigma, d) * (sigma_next - sigma)
            denoised_last = d
            ended_with_heun = False
        elif code == "F":
            sigma, sigma_next = sigmas[k], sigmas[k + 1]
            d = model(x, sigma * s_in, **_with_step(extra_args, sigma, sigma_next))
            if callback is not None:
                callback({"x": x, "i": k, "sigma": sigma, "sigma_hat": sigma, "denoised": d})
            if b <= 0.0:
                x = d
            elif eta <= 0.0 and abs(hf_scale - 1.0) <= 1e-6:
                x = x + to_d(x, sigma, d) * (sigma_next - sigma)
            else:
                eps_old = (x - (1.0 - a) * d) / a
                eps_new = noise_sampler(a, b)
                eps_mix = spectral_mix_noise(
                    eps_old, eps_new,
                    eta_low=0.0, eta_high=eta,
                    cutoff=spectral_cutoff, width=0.20,
                    hf_scale=hf_scale,
                )
                x = (1.0 - b) * d + b * eps_mix
            denoised_last = d
            ended_with_heun = False
        elif code == "H":
            b_eff = sigma_min if b <= 0.0 else b
            if k + 1 < n:
                nxt = sig_list[k + 2]
                after = sigma_min if (codes[k + 1] == "H" and nxt <= 0.0) else nxt
            else:
                after = 0.0
            d1 = model(x, a * s_in, **_with_step(extra_args, a, b_eff))
            if callback is not None:
                callback({"x": x, "i": k, "sigma": sigmas[k], "sigma_hat": sigmas[k], "denoised": d1})
            r = b_eff / a
            x2 = r * x + (1.0 - r) * d1
            told = b_eff * (1.0 - detail)
            d2 = model(x2, told * s_in, **_with_step(extra_args, told, after))
            p1, p2 = _phi(math.log(a / b_eff))
            d_bar = ((p1 - p2) * d1 + p2 * d2) / p1
            eps_old = (x - (1.0 - a) * d_bar) / a
            if late_eta > 0.0:
                eps_mix = spectral_mix_noise(
                    eps_old, noise_sampler(a, b_eff),
                    eta_low=0.0, eta_high=late_eta,
                    cutoff=late_cutoff, width=0.20,
                    hf_scale=1.0,
                )
            else:
                eps_mix = eps_old
            x = (1.0 - b_eff) * d_bar + b_eff * eps_mix
            denoised_last = d_bar
            ended_with_heun = True
        else:
            raise ValueError(f"Unknown plan step {code!r}")

    if float(sigmas[-1]) <= 0.0 and ended_with_heun and denoised_last is not None:
        x = denoised_last
    return x
