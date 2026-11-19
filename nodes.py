"""ComfyUI V3 nodes for MiniMax H3 Image realism (uniform H3Realism* node IDs, zero collision)."""
from __future__ import annotations

import math

import torch

import comfy.model_management
import comfy.sample
import comfy.samplers
import comfy.utils
import latent_preview
from comfy_api.latest import ComfyExtension, io

from .h3_sampler import MODES, sample_h3_realism

CATEGORY = "MiniMax H3 Realism"
SCHEDULES = ["simple 6 (same layout as KSampler)", "exact grid"]

ASPECTS = {
    "1:1 (Square)": (1, 1),
    "2:3 (Portrait Photo)": (2, 3),
    "3:2 (Photo)": (3, 2),
    "3:4 (Portrait Standard)": (3, 4),
    "4:3 (Standard)": (4, 3),
    "9:16 (Portrait Widescreen)": (9, 16),
    "16:9 (Widescreen)": (16, 9),
    "9:21 (Portrait Ultrawide)": (9, 21),
    "21:9 (Ultrawide)": (21, 9),
}


def _sampler(mode: str, eta: float, spectral_cutoff: float, hf_scale: float, detail: float, texture_from: float):
    return comfy.samplers.KSAMPLER(
        sample_h3_realism,
        extra_options={
            "mode": mode,
            "eta": float(eta),
            "spectral_cutoff": float(spectral_cutoff),
            "hf_scale": float(hf_scale),
            "detail": float(detail),
            "texture_from": float(texture_from),
        },
    )


def h3_grid(model) -> torch.Tensor:
    """H3 Image's distilled noise grid, descending and ending at 0, read from the checkpoint."""
    grid = getattr(model.get_model_object("model_sampling"), "grid", None)
    if grid is None:
        raise ValueError("This model has no distilled noise grid: the H3 Realism nodes are for MiniMax H3 Image.")
    return grid.flip(0).float().cpu()


def h3_sigmas(model, schedule: str) -> torch.Tensor:
    """'simple 6' matches KSampler (euler, simple, 6) layout per seed; 'exact grid' uses the exact distilled grid."""
    grid = h3_grid(model)
    if schedule.startswith("exact"):
        return grid
    return comfy.samplers.calculate_sigmas(model.get_model_object("model_sampling"), "simple", 6).cpu()


def _sampler_inputs():
    return [
        io.Combo.Input(
            "mode",
            options=MODES,
            default=MODES[0],
            tooltip=(
                "spectral 6: 6 model calls (EEFFFE) with 2D FFT frequency-split re-noising — fastest, locks "
                "low-frequency face likeness/hands while refreshing high-frequency detail. "
                "spectral + texture 8: 8 calls (EEFFHH) adding 2nd-order exponential Heun texture on the last two "
                "steps — sharpest skin, hair and T2I micro-detail. "
                "texture 8 (v1.1 classic): plain Euler above texture_from + exponential Heun below."
            ),
        ),
        io.Float.Input(
            "eta",
            default=0.85,
            min=0.0,
            max=1.0,
            step=0.01,
            advanced=True,
            tooltip=(
                "Fresh high-frequency noise share on spectral steps (0.85 default; 0 = pure deterministic Euler). "
                "In 'spectral + texture 8', the late texture steps scale proportionally (0.65 at default 0.85). "
                "In 'texture 8 (v1.1 classic)', applied directly as isotropic eta (set 0.65 for exact v1.1)."
            ),
        ),
        io.Float.Input(
            "spectral_cutoff",
            default=0.25,
            min=0.0,
            max=0.9,
            step=0.01,
            advanced=True,
            tooltip=(
                "Normalized radial frequency below which noise stays deterministically locked to Euler "
                "(protects pose, face proportions, hands and text). Higher = more locked; 0 = full-band re-noise."
            ),
        ),
        io.Float.Input(
            "hf_scale",
            default=1.0,
            min=0.75,
            max=1.15,
            step=0.01,
            advanced=True,
            tooltip=(
                "High-frequency noise amplitude multiplier on spectral steps. 1.0 preserves exact unit white noise "
                "(crispest pores & fabric); 0.92-0.96 slightly softens fine grain in T2I."
            ),
        ),
        io.Float.Input(
            "detail",
            default=0.07,
            min=0.0,
            max=0.5,
            step=0.01,
            advanced=True,
            tooltip=(
                "For 8-call modes: the second evaluation of each exponential Heun step is told a noise level "
                "this much lower, drawing leftover noise as fine pores and hair strands. 0 = off."
            ),
        ),
        io.Float.Input(
            "texture_from",
            default=0.55,
            min=0.0,
            max=1.0,
            step=0.01,
            advanced=True,
            tooltip=(
                "Used by 'texture 8 (v1.1 classic)': noise level at and below which exponential Heun runs. "
                "0 = pixel-identical to stock Euler throughout."
            ),
        ),
    ]


class H3RealismKSampler(io.ComfyNode):
    """Drop-in KSampler for MiniMax H3 Image with Frequency-Split Spectral Re-Noising."""

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="H3RealismKSampler",
            display_name="H3 Realism KSampler",
            category=CATEGORY,
            description=(
                "Drop-in KSampler for MiniMax H3 Image, tuned for photographic realism. Defaults to Spectral 6 "
                "(6 model calls): plain Euler on high-noise layout steps, then variance-preserving 2D FFT "
                "frequency-split re-noising that locks low-frequency identity/hands/text while refreshing "
                "high-frequency skin and fabric detail. Also includes Spectral + Texture 8 (richest detail) and "
                "v1.1 Classic Texture 8."
            ),
            inputs=[
                io.Model.Input("model", tooltip="MiniMax H3 Image diffusion model."),
                io.Conditioning.Input(
                    "positive",
                    tooltip="Conditioning from MiniMax H3 Image Conditioning (or H3 Realism Empty Picture for T2I). CFG is 1.",
                ),
                io.Latent.Input(
                    "latent_image",
                    tooltip="The latent from MiniMax H3 Image Conditioning (sets the output resolution).",
                ),
                io.Int.Input(
                    "seed",
                    default=0,
                    min=0,
                    max=0xFFFFFFFFFFFFFFFF,
                    control_after_generate=True,
                    tooltip="Random seed for initial noise and spectral/texture draws.",
                ),
                *_sampler_inputs(),
                io.Combo.Input(
                    "schedule",
                    options=SCHEDULES,
                    default=SCHEDULES[0],
                    advanced=True,
                    tooltip=(
                        "'simple 6' matches ComfyUI KSampler (euler, simple, 6) layout for the same seed. "
                        "'exact grid' lands directly on the checkpoint's stored PDD sigmas."
                    ),
                ),
            ],
            outputs=[io.Latent.Output()],
        )

    @classmethod
    def execute(
        cls,
        model,
        positive,
        latent_image,
        seed=0,
        mode=MODES[0],
        eta=0.85,
        spectral_cutoff=0.25,
        hf_scale=1.0,
        detail=0.07,
        texture_from=0.55,
        schedule=SCHEDULES[0],
    ) -> io.NodeOutput:
        latent = latent_image.copy()
        samples_in = comfy.sample.fix_empty_latent_channels(
            model,
            latent["samples"],
            latent.get("downscale_ratio_spacial", None),
            latent.get("downscale_ratio_temporal", None),
        )
        noise = comfy.sample.prepare_noise(samples_in, seed, latent.get("batch_index", None))
        sigmas = h3_sigmas(model, schedule)
        guider = comfy.samplers.CFGGuider(model)
        guider.inner_set_conds({"positive": positive})
        guider.set_cfg(1.0)
        callback = latent_preview.prepare_callback(model, sigmas.shape[-1] - 1, {})
        samples = guider.sample(
            noise,
            samples_in,
            _sampler(mode, eta, spectral_cutoff, hf_scale, detail, texture_from),
            sigmas,
            denoise_mask=latent.get("noise_mask", None),
            callback=callback,
            disable_pbar=not comfy.utils.PROGRESS_BAR_ENABLED,
            seed=seed,
        )
        out = latent.copy()
        out.pop("downscale_ratio_spacial", None)
        out.pop("downscale_ratio_temporal", None)
        out["samples"] = samples.to(comfy.model_management.intermediate_device())
        return io.NodeOutput(out)


class H3RealismSampler(io.ComfyNode):
    """Modular SAMPLER output for SamplerCustomAdvanced graphs (any guider, any sigmas, supports second-pass tails)."""

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="H3RealismSampler",
            display_name="H3 Realism Sampler",
            category=CATEGORY,
            description=(
                "The H3 Realism KSampler's sampler for SamplerCustomAdvanced graphs. Automatically aligns to the "
                "matching step when given partial/second-pass sigmas. Pair with H3 Realism Sigmas."
            ),
            inputs=_sampler_inputs(),
            outputs=[io.Sampler.Output()],
        )

    @classmethod
    def execute(
        cls,
        mode=MODES[0],
        eta=0.85,
        spectral_cutoff=0.25,
        hf_scale=1.0,
        detail=0.07,
        texture_from=0.55,
    ) -> io.NodeOutput:
        return io.NodeOutput(_sampler(mode, eta, spectral_cutoff, hf_scale, detail, texture_from))


class H3RealismSigmas(io.ComfyNode):
    """MiniMax H3 Image's distilled 6-step sigma schedule, read dynamically from the checkpoint."""

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="H3RealismSigmas",
            display_name="H3 Realism Sigmas",
            category=CATEGORY,
            description="Reads MiniMax H3 Image's distilled 6-step sigma schedule directly from the model.",
            inputs=[
                io.Model.Input("model", tooltip="MiniMax H3 Image diffusion model."),
                io.Combo.Input(
                    "schedule",
                    options=SCHEDULES,
                    default=SCHEDULES[0],
                    tooltip=(
                        "'simple 6' matches KSampler (euler, simple, 6) layout per seed; "
                        "'exact grid' uses the exact stored distilled grid."
                    ),
                ),
            ],
            outputs=[io.Sigmas.Output()],
        )

    @classmethod
    def execute(cls, model, schedule=SCHEDULES[0]) -> io.NodeOutput:
        return io.NodeOutput(h3_sigmas(model, schedule))


class H3RealismEmptyPicture(io.ComfyNode):
    """Text-to-image mode switch: prepends an empty black 512 px picture's vision tokens on early steps.

    Without any picture in its conditioning, H3 Image renders in a crusty, over-sharpened text-only mode.
    Prepending a black 512 px picture's vision tokens on the first steps switches it cleanly into its
    photographic reference regime with no reference latent. Edit-mode conditioning (already containing
    vision tokens) is passed through untouched.

    Port of Kijai's 'text with empty image' mode (ComfyUI-KJNodes, GPL-3.0).
    """

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="H3RealismEmptyPicture",
            display_name="H3 Realism Empty Picture (T2I)",
            category=CATEGORY,
            description=(
                "Switches MiniMax H3 Image text-to-image out of its crusty text-only mode by prepending a black "
                "512 px picture's vision tokens on the first steps (no reference latent, prompt never mentions it). "
                "Leaves edit conditioning with real pictures untouched. Port of Kijai's KJNodes trick."
            ),
            inputs=[
                io.Clip.Input("clip", tooltip="The MiniMax H3 text encoder used by MiniMax H3 Image Conditioning."),
                io.Conditioning.Input(
                    "positive",
                    tooltip="Conditioning from MiniMax H3 Image Conditioning (with no pictures connected for T2I).",
                ),
                io.Float.Input(
                    "start",
                    default=0.0,
                    min=0.0,
                    max=1.0,
                    step=0.001,
                    advanced=True,
                    tooltip="Start of the sampling range that sees the empty picture (0.0 = step 0).",
                ),
                io.Float.Input(
                    "end",
                    default=0.25,
                    min=0.0,
                    max=1.0,
                    step=0.001,
                    advanced=True,
                    tooltip=(
                        "End of the range seeing the empty picture. 0.25 covers steps 0-1 (cleanest skin and "
                        "landscapes); 0.10 covers step 0 only (half the token overhead, slightly crisper hair)."
                    ),
                ),
            ],
            outputs=[io.Conditioning.Output(display_name="positive")],
        )

    @classmethod
    def execute(cls, clip, positive, start=0.0, end=0.25) -> io.NodeOutput:
        if end <= start:
            return io.NodeOutput(positive)
        picture, extra = clip.encode_from_tokens_scheduled(
            clip.tokenize("", images=[torch.zeros(1, 512, 512, 3)], picture_label="Picture %d: ")
        )[0]
        picture_tags = extra.get("minimax_token_tags")
        out = []
        for cond, d in positive:
            tags = d.get("minimax_token_tags")
            if picture_tags is None or tags is None:
                raise ValueError(
                    "H3 Realism Empty Picture needs the MiniMax H3 text encoder and MiniMax H3 Image Conditioning."
                )
            if (tags == 0).any():  # vision tokens already present (edit mode or already switched)
                out.append([cond, d])
                continue
            with_picture = torch.cat([picture.to(device=cond.device, dtype=cond.dtype), cond], dim=1)
            all_tags = torch.cat([picture_tags.to(tags.device), tags])
            out.append([with_picture, {**d, "minimax_token_tags": all_tags, "start_percent": start, "end_percent": end}])
            if start > 0.0:
                out.append([cond, {**d, "start_percent": 0.0, "end_percent": start}])
            if end < 1.0:
                out.append([cond, {**d, "start_percent": end, "end_percent": 1.0}])
        return io.NodeOutput(out)


class H3RealismResolutionSelector(io.ComfyNode):
    """Aspect-ratio + megapixel resolution selector tuned to H3 Image's tested resolution range."""

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="H3RealismResolutionSelector",
            display_name="H3 Realism Resolution Selector",
            category=CATEGORY,
            description=(
                "Calculates width and height from aspect ratio and megapixels (1 MP = 1024 x 1024 px), removing "
                "ComfyUI's 16 MP cap. Practical photographic range for H3 Image is 16-64 MP; 96 MP is the verified "
                "clean ceiling (128+ MP breaks fine textures into 32 px token blocks)."
            ),
            inputs=[
                io.Combo.Input(
                    "aspect_ratio",
                    options=list(ASPECTS),
                    default="2:3 (Portrait Photo)",
                    tooltip="Target aspect ratio.",
                ),
                io.Float.Input(
                    "megapixels",
                    default=16.0,
                    min=1.0,
                    max=179.0,
                    step=0.5,
                    tooltip=(
                        "Target megapixels (1 MP = 1024 x 1024 px): 16 MP = 4096x4096 (1:1) or 3360x5024 (2:3); "
                        "64 MP = 8192x8192; 96 MP is H3's verified clean ceiling (128+ MP shows 32 px blocks)."
                    ),
                ),
                io.Int.Input(
                    "multiple",
                    default=32,
                    min=8,
                    max=128,
                    step=4,
                    advanced=True,
                    tooltip="Round width and height to this multiple (32 = one MiniMax H3 Image token).",
                ),
                io.ResolutionPreview.Input("preview", tooltip="Live preview of the calculated output resolution."),
            ],
            outputs=[io.Int.Output("width"), io.Int.Output("height")],
        )

    @classmethod
    def execute(cls, aspect_ratio="2:3 (Portrait Photo)", megapixels=16.0, multiple=32, preview=None) -> io.NodeOutput:
        w, h = ASPECTS[aspect_ratio]
        scale = math.sqrt(float(megapixels) * 1024 * 1024 / (w * h))
        m = int(multiple)
        return io.NodeOutput(max(m, round(w * scale / m) * m), max(m, round(h * scale / m) * m))


NODES = [
    H3RealismKSampler,
    H3RealismSampler,
    H3RealismSigmas,
    H3RealismEmptyPicture,
    H3RealismResolutionSelector,
]


class H3RealismExtension(ComfyExtension):
    async def get_node_list(self):
        return NODES


async def comfy_entrypoint():
    return H3RealismExtension()
