"""ComfyUI nodes for the H3 Image sampler (classic node API)."""
from __future__ import annotations

import torch

import comfy.model_management
import comfy.sample
import comfy.samplers
import comfy.utils
import latent_preview

from .h3_sampler import sample_h3

# The tested recipe. These sit under "advanced inputs": the defaults are what the tests settled on.
TEXTURE_INPUTS = {
    "texture_from": ("FLOAT", {"default": 0.55, "min": 0.0, "max": 1.0, "step": 0.01, "advanced": True,
                               "tooltip": "Noise level at and below which steps draw texture. Above it, plain Euler on H3's "
                                          "distilled grid sets structure and identity. 0 = stock Euler throughout."}),
    "eta": ("FLOAT", {"default": 0.65, "min": 0.0, "max": 1.0, "step": 0.01, "advanced": True,
                      "tooltip": "Share of the noise replaced with fresh noise on texture steps (0.65 = 42% of the variance)."}),
    "detail": ("FLOAT", {"default": 0.07, "min": 0.0, "max": 0.5, "step": 0.01, "advanced": True,
                         "tooltip": "On texture steps the second evaluation is told a noise level this much lower, so it "
                                    "draws leftover noise as fine detail. 0 = off."}),
}
SCHEDULES = ["simple 6 (same layout as KSampler)", "exact grid"]


def _sampler(texture_from, eta, detail):
    return comfy.samplers.KSAMPLER(sample_h3, extra_options={"texture_from": texture_from, "eta": eta, "detail": detail})


def h3_grid(model) -> torch.Tensor:
    """H3 Image's distilled noise grid, descending and ending at 0, read from the checkpoint."""
    grid = getattr(model.get_model_object("model_sampling"), "grid", None)
    if grid is None:
        raise ValueError("This model has no distilled noise grid: the H3 Image nodes are for MiniMax H3 Image.")
    return grid.flip(0).float().cpu()


def h3_sigmas(model, schedule: str) -> torch.Tensor:
    """"simple 6" is ComfyUI's simple scheduler at 6 steps: within ~0.001 of the grid and what KSampler uses,
    so a seed gives the same layout as KSampler (euler, simple, 6). "exact grid" lands on the distilled
    levels exactly; the layout then differs a little from KSampler's."""
    grid = h3_grid(model)
    if schedule.startswith("exact"):
        return grid
    return comfy.samplers.calculate_sigmas(model.get_model_object("model_sampling"), "simple", 6).cpu()


class H3ImageKSampler:
    """Drop-in KSampler for MiniMax H3 Image."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",),
            "positive": ("CONDITIONING", {"tooltip": "From MiniMax H3 Image Conditioning. cfg is 1: no negative needed."}),
            "latent_image": ("LATENT", {"tooltip": "The latent from MiniMax H3 Image Conditioning (it sets the output size)."}),
            "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff, "control_after_generate": True}),
            **TEXTURE_INPUTS,
            "schedule": (SCHEDULES, {"advanced": True}),
        }}

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "sample"
    CATEGORY = "sampling"
    DESCRIPTION = ("KSampler for MiniMax H3 Image, tuned for realism. Structure: plain Euler on the model's distilled "
                   "6-step grid (the same layout as KSampler euler/simple/6 for the same seed, no duplicated objects). "
                   "Texture: the last two steps use a second-order step with fresh noise and extra detail for "
                   "photographic skin and hair. 8 model calls.")

    def sample(self, model, positive, latent_image, seed, texture_from=0.55, eta=0.65, detail=0.07, schedule=SCHEDULES[0]):
        latent = latent_image.copy()
        samples_in = comfy.sample.fix_empty_latent_channels(model, latent["samples"], latent.get("downscale_ratio_spacial", None),
                                                            latent.get("downscale_ratio_temporal", None))
        noise = comfy.sample.prepare_noise(samples_in, seed, latent.get("batch_index", None))
        sigmas = h3_sigmas(model, schedule)
        guider = comfy.samplers.CFGGuider(model)
        guider.inner_set_conds({"positive": positive})
        guider.set_cfg(1.0)
        callback = latent_preview.prepare_callback(model, sigmas.shape[-1] - 1, {})
        samples = guider.sample(noise, samples_in, _sampler(texture_from, eta, detail), sigmas,
                                denoise_mask=latent.get("noise_mask", None), callback=callback,
                                disable_pbar=not comfy.utils.PROGRESS_BAR_ENABLED, seed=seed)
        out = latent.copy()
        out.pop("downscale_ratio_spacial", None)
        out.pop("downscale_ratio_temporal", None)
        out["samples"] = samples.to(comfy.model_management.intermediate_device())
        return (out,)


class H3ImageSampler:
    """The same sampler as a SAMPLER, for SamplerCustomAdvanced graphs (any guider, any sigmas)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": dict(TEXTURE_INPUTS)}

    RETURN_TYPES = ("SAMPLER",)
    FUNCTION = "get_sampler"
    CATEGORY = "sampling/custom_sampling/samplers"
    DESCRIPTION = "The H3 Image KSampler's sampler, for SamplerCustomAdvanced. Use it with H3 Image Sigmas."

    def get_sampler(self, texture_from, eta, detail):
        return (_sampler(texture_from, eta, detail),)


class H3ImageSigmas:
    """H3 Image's own distilled schedule."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"model": ("MODEL",), "schedule": (SCHEDULES,)}}

    RETURN_TYPES = ("SIGMAS",)
    FUNCTION = "get_sigmas"
    CATEGORY = "sampling/custom_sampling/schedulers"

    def get_sigmas(self, model, schedule):
        return (h3_sigmas(model, schedule),)


NODE_CLASS_MAPPINGS = {
    "H3ImageKSampler": H3ImageKSampler,
    "H3ImageSampler": H3ImageSampler,
    "H3ImageSigmas": H3ImageSigmas,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "H3ImageKSampler": "H3 Image KSampler",
    "H3ImageSampler": "H3 Image Sampler",
    "H3ImageSigmas": "H3 Image Sigmas",
}
