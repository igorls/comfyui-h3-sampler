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


class H3ImageEmptyPicture:
    """Text to image: puts an empty picture's vision tokens in front of the prompt on the first steps.

    With no picture in its conditioning, H3 Image renders in a text-only mode that comes out crusty and
    over-sharpened at 100%; any picture switches it to its much cleaner reference mode. This adds only the vision
    tokens of a black 512 px picture, and only on the structure steps, which is enough to switch modes and cheaper
    than wiring a real picture through the conditioning node (no reference latent, no extra tokens on the texture
    steps).

    A port of the "text with empty image" mode of Kijai's MiniMax H3 Prompt Weight node (ComfyUI-KJNodes, GPL-3.0).
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "clip": ("CLIP", {"tooltip": "The MiniMax H3 text encoder, the same one the conditioning node uses."}),
            "positive": ("CONDITIONING", {"tooltip": "From MiniMax H3 Image Conditioning with no pictures connected."}),
            "start": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.001, "advanced": True,
                                "tooltip": "Start of the sampling range that sees the empty picture."}),
            "end": ("FLOAT", {"default": 0.25, "min": 0.0, "max": 1.0, "step": 0.001, "advanced": True,
                              "tooltip": "End of that range. 0.25 covers the first two of the 6 steps, which is enough."}),
        }}

    RETURN_TYPES = ("CONDITIONING",)
    RETURN_NAMES = ("positive",)
    FUNCTION = "apply"
    CATEGORY = "conditioning"
    DESCRIPTION = ("Text to image with MiniMax H3 Image: adds an empty picture's vision tokens on the first steps, which "
                   "switches H3 to its cleaner reference mode (no crusty, over-sharpened skin). The prompt never "
                   "mentions the picture. Leaves conditioning that already has a picture as it is. Port of Kijai's "
                   "'text with empty image' mode (KJNodes).")

    def apply(self, clip, positive, start=0.0, end=0.25):
        if end <= start:
            return (positive,)
        # the H3 encoder is causal and not chat-templated, so "Picture 1: <vision block>" encodes the same in front
        # of any prompt and can be put in front of the already encoded prompt
        picture, extra = clip.encode_from_tokens_scheduled(
            clip.tokenize("", images=[torch.zeros(1, 512, 512, 3)], picture_label="Picture %d: "))[0]
        picture_tags = extra.get("minimax_token_tags")
        out = []
        for cond, d in positive:
            tags = d.get("minimax_token_tags")
            if picture_tags is None or tags is None:
                raise ValueError("H3 Image Empty Picture needs the MiniMax H3 text encoder and MiniMax H3 Image "
                                 "Conditioning.")
            if (tags == 0).any():  # vision tokens already there: it is an edit, or already switched
                out.append([cond, d])
                continue
            with_picture = torch.cat([picture.to(device=cond.device, dtype=cond.dtype), cond], dim=1)
            all_tags = torch.cat([picture_tags.to(tags.device), tags])
            out.append([with_picture, {**d, "minimax_token_tags": all_tags, "start_percent": start, "end_percent": end}])
            if start > 0.0:
                out.append([cond, {**d, "start_percent": 0.0, "end_percent": start}])
            if end < 1.0:
                out.append([cond, {**d, "start_percent": end, "end_percent": 1.0}])
        return (out,)


NODE_CLASS_MAPPINGS = {
    "H3ImageKSampler": H3ImageKSampler,
    "H3ImageSampler": H3ImageSampler,
    "H3ImageSigmas": H3ImageSigmas,
    "H3ImageEmptyPicture": H3ImageEmptyPicture,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "H3ImageKSampler": "H3 Image KSampler",
    "H3ImageSampler": "H3 Image Sampler",
    "H3ImageSigmas": "H3 Image Sigmas",
    "H3ImageEmptyPicture": "H3 Image Empty Picture (text to image)",
}
