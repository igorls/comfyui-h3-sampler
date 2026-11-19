#!/usr/bin/env python3
"""CPU-only unit and integration tests for comfyui-h3-sampler v2.

Run against any ComfyUI checkout with MiniMax H3 Image support:

    COMFYUI_PATH=/path/to/ComfyUI python tests/test_h3_realism.py
"""
from __future__ import annotations

import asyncio
import importlib
import json
import os
import sys
from pathlib import Path

os.environ["CUDA_VISIBLE_DEVICES"] = ""

PACK = Path(__file__).resolve().parent.parent
COMFY = Path(os.environ.get("COMFYUI_PATH") or PACK.parent.parent)
sys.path.insert(0, str(COMFY))
sys.path.insert(0, str(PACK.parent))

from comfy.cli_args import args as cargs  # noqa: E402
cargs.cpu = True

import torch  # noqa: E402
from comfy.k_diffusion.sampling import sample_euler  # noqa: E402

# Import the pack cleanly even if its directory contains hyphens
spec = importlib.util.spec_from_file_location("comfyui_h3_sampler", PACK / "__init__.py",
                                              submodule_search_locations=[str(PACK)])
pkg = importlib.util.module_from_spec(spec)
sys.modules["comfyui_h3_sampler"] = pkg
spec.loader.exec_module(pkg)

S = importlib.import_module("comfyui_h3_sampler.h3_sampler")
N = importlib.import_module("comfyui_h3_sampler.nodes")

OK: list[bool] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    OK.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + (f"  {detail}" if detail else ""), flush=True)


class StubModel:
    """Deterministic stub matching ComfyUI's model wrapper contract."""

    def __init__(self, grid=S.OFFICIAL_SIGMAS, sigma_min=1e-4):
        ms = type("MS", (), {"grid": torch.tensor(list(reversed(grid)), dtype=torch.float32), "sigma_min": sigma_min})()
        self.inner_model = type("I", (), {"inner_model": type("M", (), {"model_sampling": ms})()})()
        self.calls: list[tuple[float, list[float] | None]] = []

    def __call__(self, x, sigma, **kwargs):
        to = kwargs.get("model_options", {}).get("transformer_options", {})
        ss = to.get("sample_sigmas")
        self.calls.append((float(sigma.flatten()[0]), ss.tolist() if ss is not None else None))
        return 0.25 + 0.15 * torch.tanh(x)


def test_spectral_math():
    g = torch.Generator().manual_seed(123)
    e_old = torch.randn(1, 24, 1, 64, 64, generator=g)
    e_new = torch.randn(1, 24, 1, 64, 64, generator=g)

    # Identity boundary
    same = S.spectral_mix_noise(e_old, e_new, eta_low=0.0, eta_high=0.0, hf_scale=1.0)
    check("spectral: eta=0 returns exact eps_old", torch.allclose(same, e_old, atol=1e-6))

    # Full fresh boundary
    fresh = S.spectral_mix_noise(e_old, e_new, eta_low=1.0, eta_high=1.0, hf_scale=1.0)
    check("spectral: eta=1 returns exact eps_new", torch.allclose(fresh, e_new, atol=1e-6))

    # Variance-preserving unit white Gaussian marginal + frequency selectivity
    mix = S.spectral_mix_noise(e_old, e_new, eta_low=0.0, eta_high=1.0, cutoff=0.25, width=0.20, hf_scale=1.0)
    std = float(mix.std())
    check("spectral: preserves unit variance N(0, I)", abs(std - 1.0) < 0.02, f"std={std:.4f}")

    # Verify low frequencies match e_old (>0.999) and high frequencies match e_new (>0.99)
    r = S._radial_freq_grid(64, 64, mix.device)
    f_old = torch.fft.rfft2(e_old.float(), norm="ortho")
    f_new = torch.fft.rfft2(e_new.float(), norm="ortho")
    f_mix = torch.fft.rfft2(mix.float(), norm="ortho")
    lo = r <= 0.20
    hi = r >= 0.50
    lo_err = float((f_mix[..., lo] - f_old[..., lo]).abs().max())
    hi_err = float((f_mix[..., hi] - f_new[..., hi]).abs().max())
    check("spectral: low frequencies (<0.20) locked exactly to eps_old", lo_err < 1e-5, f"max_err={lo_err:.2e}")
    check("spectral: high frequencies (>0.50) taken directly from eps_new", hi_err < 1e-5, f"max_err={hi_err:.2e}")


def test_sampler_modes_and_parity():
    sig = torch.tensor(S.OFFICIAL_SIGMAS, dtype=torch.float32)
    x0 = torch.randn(1, 24, 1, 16, 16, generator=torch.Generator().manual_seed(7))

    # Euler parity: classic with texture_from=0 == ComfyUI sample_euler
    ref = sample_euler(StubModel(), x0.clone(), sig, extra_args={}, disable=True)
    m_classic_off = StubModel()
    got_classic_off = S.sample_h3_realism(
        m_classic_off, x0.clone(), sig, extra_args={"seed": 7}, disable=True,
        mode=S.MODES[2], texture_from=0.0,
    )
    check("parity: classic texture_from=0 == sample_euler", torch.allclose(got_classic_off, ref, atol=1e-6))
    check("parity: classic texture_from=0 makes 6 calls", len(m_classic_off.calls) == 6)

    # Euler parity: spectral 6 with eta=0 == ComfyUI sample_euler
    m_spec_off = StubModel()
    got_spec_off = S.sample_h3_realism(
        m_spec_off, x0.clone(), sig, extra_args={"seed": 7}, disable=True,
        mode=S.MODES[0], eta=0.0, hf_scale=1.0,
    )
    check("parity: spectral 6 with eta=0 == sample_euler", torch.allclose(got_spec_off, ref, atol=1e-6))

    # NFE counts & explicit sample_sigmas on every call
    for mode, expected_nfe in ((S.MODES[0], 6), (S.MODES[1], 8), (S.MODES[2], 8)):
        m = StubModel()
        out = S.sample_h3_realism(m, x0.clone(), sig, extra_args={"seed": 7}, disable=True, mode=mode)
        check(f"mode '{mode}': {expected_nfe} model calls, finite output",
              len(m.calls) == expected_nfe and bool(torch.isfinite(out).all()),
              f"calls={len(m.calls)}")
        check(f"mode '{mode}': every call sets 2-element sample_sigmas",
              all(ss is not None and len(ss) == 2 for _, ss in m.calls))

    # Mid-schedule / second-pass tail alignment
    tail_from_3 = S.plan_for_sigmas("EEFFFE", list(S.OFFICIAL_SIGMAS[3:]))
    tail_from_4 = S.plan_for_sigmas("EEFFHH", list(S.OFFICIAL_SIGMAS[4:]))
    check("second-pass: EEFFFE starting at sigma 0.75 runs FFE", "".join(tail_from_3) == "FFE", str(tail_from_3))
    check("second-pass: EEFFHH starting at sigma 0.533 runs HH", "".join(tail_from_4) == "HH", str(tail_from_4))

    m_tail = StubModel()
    out_tail = S.sample_h3_realism(m_tail, x0.clone(), sig[3:], extra_args={"seed": 7}, disable=True, mode=S.MODES[0])
    check("second-pass: spectral 6 tail (3 steps) makes 3 finite calls",
          len(m_tail.calls) == 3 and bool(torch.isfinite(out_tail).all()))


def test_v3_nodes_and_collisions():
    ext = asyncio.run(pkg.comfy_entrypoint())
    nodes = asyncio.run(ext.get_node_list())
    ids = [n.define_schema().node_id for n in nodes]
    expected = [
        "H3RealismEmptyPicture",
        "H3RealismKSampler",
        "H3RealismResolutionSelector",
        "H3RealismSampler",
        "H3RealismSigmas",
    ]
    check("nodes: all 5 V3 schemas registered with H3Realism* prefix", sorted(ids) == expected, str(ids))

    # Zero collision with generic H3Image* node IDs used by other community packs
    generic_h3_ids = {"H3ImageSampler", "H3ImageSteering", "H3ImageResolutionSelector"}
    check("nodes: zero collision with generic H3Image* node IDs", not (set(ids) & generic_h3_ids))

    # Every input carries a tooltip
    missing_tips = [
        f"{n.define_schema().node_id}.{inp.id}"
        for n in nodes
        for inp in n.define_schema().inputs
        if not getattr(inp, "tooltip", None)
    ]
    check("nodes: every input has a tooltip", not missing_tips, str(missing_tips))

    # Resolution selector math & 32-pixel alignment
    rs = N.H3RealismResolutionSelector
    cases = [
        ("1:1 (Square)", 16.0, (4096, 4096)),
        ("2:3 (Portrait Photo)", 16.0, (3360, 5024)),
        ("3:2 (Photo)", 16.0, (5024, 3360)),
        ("1:1 (Square)", 64.0, (8192, 8192)),
        ("2:3 (Portrait Photo)", 96.0, (8192, 12288)),
    ]
    all_ok = True
    for ratio, mp, want in cases:
        got = rs.execute(ratio, mp, 32).args
        if got != want or got[0] % 32 != 0 or got[1] % 32 != 0:
            all_ok = False
            print(f"  mismatch {ratio} {mp}MP: got {got}, want {want}")
    check("nodes: H3RealismResolutionSelector exact 32px multiples up to 96+ MP", all_ok)

    # Empty picture conditioning behavior (T2I vs edit passthrough)
    class FakeClip:
        def tokenize(self, text, images=None, picture_label=None):
            return {"images": images}

        def encode_from_tokens_scheduled(self, tokens):
            return [(torch.ones(1, 4, 16), {"minimax_token_tags": torch.zeros(4, dtype=torch.long)})]

    t2i_cond = [(torch.zeros(1, 10, 16), {"minimax_token_tags": torch.ones(10, dtype=torch.long)})]
    out_t2i = N.H3RealismEmptyPicture.execute(FakeClip(), t2i_cond, start=0.0, end=0.25).args[0]
    check("nodes: EmptyPicture splits T2I into [0..0.25 with vision tokens, 0.25..1.0 plain]",
          len(out_t2i) == 2 and out_t2i[0][0].shape[1] == 14 and out_t2i[1][0].shape[1] == 10
          and out_t2i[0][1]["end_percent"] == 0.25 and out_t2i[1][1]["start_percent"] == 0.25)

    edit_tags = torch.cat([torch.zeros(4, dtype=torch.long), torch.ones(10, dtype=torch.long)])
    edit_cond = [(torch.zeros(1, 14, 16), {"minimax_token_tags": edit_tags})]
    out_edit = N.H3RealismEmptyPicture.execute(FakeClip(), edit_cond, start=0.0, end=0.25).args[0]
    check("nodes: EmptyPicture leaves edit conditioning untouched",
          len(out_edit) == 1 and out_edit[0][0].shape[1] == 14)


def test_example_workflows():
    wf_dir = PACK / "example_workflows"
    wfs = sorted(wf_dir.glob("*.json"))
    check("workflows: both example workflows present", len(wfs) >= 2, str([p.name for p in wfs]))
    for p in wfs:
        data = json.loads(p.read_text(encoding="utf-8"))
        types = {n["type"] for n in data["nodes"]}
        old_ids = types & {"H3ImageKSampler", "H3ImageSampler", "H3ImageSigmas", "H3ImageEmptyPicture"}
        check(f"workflow '{p.name}': uses H3Realism* IDs (no legacy H3Image* IDs)", not old_ids, str(old_ids))
        # Verify widgets_values matches widgets_values_named
        mismatches = []
        for n in data["nodes"]:
            named, vals = n.get("widgets_values_named"), n.get("widgets_values")
            if isinstance(named, dict) and isinstance(vals, list):
                for i, (k, v) in enumerate(named.items()):
                    if i < len(vals) and vals[i] != v:
                        mismatches.append(f"{n['type']}#{n['id']}.{k}: {vals[i]!r} != {v!r}")
        check(f"workflow '{p.name}': widgets_values matches widgets_values_named", not mismatches, str(mismatches))


if __name__ == "__main__":
    test_spectral_math()
    test_sampler_modes_and_parity()
    test_v3_nodes_and_collisions()
    test_example_workflows()
    print(f"\n{sum(OK)} / {len(OK)} passed", flush=True)
    sys.exit(0 if all(OK) else 1)
