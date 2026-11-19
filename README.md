# H3 Realism Sampler for ComfyUI

**[Live 1:1 Interactive Showcase →](https://igorls.github.io/comfyui-h3-sampler/)**

Photographic realism nodes for **MiniMax H3 Image** in ComfyUI (V3 API, zero dependencies beyond ComfyUI):

- **H3 Realism KSampler** — drop-in KSampler with **Frequency-Split Spectral Re-Noising** (6-step fast mode and 8-step max-detail mode) on H3's distilled 6-step grid.
- **H3 Realism Empty Picture (T2I)** — switches text-to-image out of H3's crusty text-only mode with native vision tokens, keeping crisp skin pores and individual hair strands.
- **H3 Realism Resolution Selector** — aspect ratio + megapixel selector removing ComfyUI's 16 MP cap, tuned to H3's tested 16–64 MP practical range and 96 MP clean ceiling.
- **H3 Realism Sampler** & **H3 Realism Sigmas** — modular `SamplerCustomAdvanced` nodes with automatic mid-schedule alignment for second-pass refinement.

> **Upgrading from v1.x?** In v2.0.0 all node IDs moved to the uniform `H3Realism*` prefix (`H3RealismKSampler`, `H3RealismSampler`, `H3RealismSigmas`, `H3RealismEmptyPicture`, `H3RealismResolutionSelector`) so this pack installs cleanly alongside other MiniMax H3 node packs with zero node ID collisions. Re-import the updated v2.0 workflows from `example_workflows/` (or ComfyUI's template browser).

## Install

Inside `ComfyUI/custom_nodes`:

```bash
git clone https://github.com/igorls/comfyui-h3-sampler
```

Then restart ComfyUI. Requires ComfyUI `>= 0.45.0` with MiniMax H3 Image support (tested on `0.45.6`).

## What's new in v2.0: Frequency-Split Spectral Re-Noising

H3 Image is step-distilled on a fixed 6-step noise grid (`1, .9675, .8875, .75, .5328, .232, 0`), with one output head per interval. Standard sampling runs into a tension:
- **Plain Euler** locks structure cleanly, but can look slightly flat on smooth skin or leave early noise commitments intact.
- **Full-band re-noising** (like `lcm` / `SSRRRS` / `euler_ancestral` on mid steps) replaces *all* spatial frequencies at once—smoothing away pores and fabric weave, and mutating hands, props, or facial structure in photo edits.

**Frequency-Split Spectral Re-Noising** resolves that tension in the 2D FFT domain:
- Below `spectral_cutoff` (default `0.25`, covering pose, face proportions, hands, props and text), the noise stays **deterministically locked to Euler**.
- Above `spectral_cutoff` (fine texture scale), fresh Gaussian noise is mixed in with a variance-preserving raised-cosine blend (`sqrt(1 - η(f)²)·E_old + η(f)·E_new`), preserving an **exact unit white-noise spectrum `N(0, I)`** so H3's distilled PDD heads stay 100% in-distribution.
- Every model call receives its exact `[told, target]` interval in `sample_sigmas`, so H3 always selects the right distilled head.

Three recipes are available in the `mode` dropdown:

| Mode | Calls | Plan | Best for |
|---|---|---|---|
| **`spectral 6 (fast, highest likeness)`** *(default)* | **6** | `EEFFFE` | **Photo edits & fast T2I** — beats v1.1 on InsightFace edit likeness while running 25–45% faster, with 100% locked hands/layout and real pores & fabric weave. |
| **`spectral + texture 8 (richest detail)`** | **8** | `EEFFHH` | **Max-detail T2I & portraits** — spectral mid steps + 2nd-order exponential Heun (`detail = 0.07`) on the last two steps for the sharpest individual hairs and pores. |
| **`texture 8 (v1.1 classic)`** | **8** | Euler → Exp-Heun | Exact v1.1 recipe. With `texture_from = 0`, pixel-identical to ComfyUI `KSampler (euler, simple, 6)`. |

## Nodes

All nodes live under the **`MiniMax H3 Realism`** category:

| Node (`node_id`) | Output | Use |
|---|---|---|
| **H3 Realism KSampler** (`H3RealismKSampler`) | `LATENT` | Drop-in KSampler for H3 Image: `model`, `positive`, `latent_image`, `seed`, `mode`. |
| **H3 Realism Sampler** (`H3RealismSampler`) | `SAMPLER` | Modular sampler for `SamplerCustomAdvanced` (supports second-pass/tail sigmas automatically). |
| **H3 Realism Sigmas** (`H3RealismSigmas`) | `SIGMAS` | Reads H3's distilled 6-step schedule directly from the model (`simple 6` or `exact grid`). |
| **H3 Realism Empty Picture (T2I)** (`H3RealismEmptyPicture`) | `CONDITIONING` | Prepends a black 512 px picture's vision tokens on steps 0–1 (`end = 0.25`, or `0.10` for step 0 only) to keep T2I out of H3's crusty text-only mode. Leaves edit conditioning untouched. |
| **H3 Realism Resolution Selector** (`H3RealismResolutionSelector`) | `width`, `height` | Aspect ratio + megapixels (`1 MP = 1024×1024 px`), rounded to multiples of 32, up to 179 MP (practical range: 16–64 MP; verified clean ceiling: 96 MP). |

Advanced inputs on `H3RealismKSampler` / `H3RealismSampler`:

| Input | Default | What it does |
|---|---|---|
| `eta` | `0.85` | High-frequency fresh-noise share on spectral steps (`0` = pure Euler). In `spectral + texture 8`, late Heun steps scale proportionally (`0.65` at default `0.85`). |
| `spectral_cutoff` | `0.25` | Normalized radial frequency below which noise stays locked to Euler (protects structure/likeness/text). |
| `hf_scale` | `1.0` | High-frequency noise amplitude on spectral steps (`1.0` = exact white noise, sharpest pores/weave; `0.92–0.96` = slightly softer T2I grain). |
| `detail` | `0.07` | On 8-call modes, the second evaluation of each exponential Heun step is told a noise level 7% lower. `0` = off. |
| `texture_from` | `0.55` | Used by `texture 8 (v1.1 classic)`: noise threshold below which exponential Heun runs (`0` = stock Euler). |
| `schedule` | `simple 6` | `simple 6` matches `KSampler (euler, simple, 6)` layout per seed; `exact grid` uses the stored checkpoint grid directly. |

## Example workflows

Both appear in ComfyUI's template browser under this pack, with canvas notes and official Comfy-Org model download metadata:

- `H3 Image - realism edit.json` — 16 MP photo edit using Picture 1 + face close-up Picture 2, `H3 Realism Resolution Selector`, and `H3 Realism KSampler` (`spectral 6`).
- `H3 Image - realism text to image.json` — 16 MP text-to-image using `H3 Realism Empty Picture`, `H3 Realism Resolution Selector`, and `H3 Realism KSampler` (`spectral + texture 8`).

## Benchmarks & Tested Findings

Tested on an RTX PRO 6000 Blackwell (96 GB), ComfyUI `0.45.6`, `minimax_h3_image_pruned_int8_convrot`:

- **Photo edits (`p2`, `p4`, `p6` at 16 MP, seed 5000, InsightFace likeness to input face):**
  - `spectral 6` (`EEFFFE`, 6 calls): mean likeness **0.525** (`0.487` / `0.658` / `0.429`), beating v1.1 `texture 8` (**0.508**: `0.477` / `0.621` / `0.426`) on every shot while running **25–45% faster** and keeping identical hands, props, pores, and fabric weave.
  - Full-band mid re-noising (`SSRRRS`, `s_noise = 0.95`) smoothed skin into plastic on `p2` and mutated bare hands into leather gloves on `p6`.
- **Text-to-image (`t4_elder` portrait & `t7_lake` landscape at 16 MP, 3×3 Laplacian fine-detail RMS):**
  - Plain T2I (no empty picture): crusty (`t7_lake` 34.8, `t4_elder` 13.7).
  - `H3 Realism Empty Picture` (`end = 0.25`) + `texture 8`: clean (`11.8` / `7.85`), organic pores and sharp individual beard hairs. Step-0-only (`end = 0.10`) keeps the same clean mode at half vision-token overhead (`13.4` / `8.80`).
  - `H3 Realism Empty Picture` (`end = 0.10`) + `spectral + texture 8`: `t4_elder` `7.93` (`hf/mid = 0.0659`) with razor-sharp beard strands and zero halos.
- **Resolution sweep (Lab 1, 4 MP → 179 MP):**
  - Practical range is **16–64 MP**; quality holds cleanly to **96 MP** (`8000×12000` / `8192×12288`). From **128 MP** upward, H3's area-normalized RoPE coordinate grid compresses neighbor spacing below `0.10` and fine textures (stripes, hair, knit) break into 32 px token blocks regardless of VRAM, attention kernel, or checkpoint precision.
- **CPU test suite:** run `COMFYUI_PATH=/path/to/ComfyUI python tests/test_h3_realism.py` to verify spectral white-noise invariants, Euler parity, PDD head routing, second-pass tail alignment, V3 schemas, collision checks, and workflow JSON consistency without a GPU.

## License

GPL-3.0, like ComfyUI.

Credits: MiniMax H3 Image by MiniMax, ComfyUI, RES4LYF by ClownsharkBatwing (whose samplers our exponential Heun pass was developed alongside), and Kijai (ComfyUI-KJNodes), whose "text with empty image" mode `H3RealismEmptyPicture` ports.
