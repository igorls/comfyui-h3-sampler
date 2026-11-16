# H3 Image KSampler for ComfyUI

A KSampler for **MiniMax H3 Image**, tuned for photographic realism. One node does what a stock ComfyUI +
RES4LYF chain of ten nodes does, with the same skin, hair and texture at 100%. Its defaults are the
tested recipe. No dependencies beyond ComfyUI.

## Install

Inside `ComfyUI/custom_nodes`:

```bash
git clone https://github.com/igorls/comfyui-h3-sampler
```

Then restart ComfyUI. It needs a ComfyUI with MiniMax H3 Image support (tested on 0.45.3).

## What it does

H3 Image is step-distilled: it has one output head per interval of a fixed 6-step noise grid
(1, .9675, .8875, .75, .5328, .232, 0), and each model call picks its head from the noise level.

- **Structure** (composition, objects, faces) is set at high noise. The node uses plain Euler on H3's
  6-step schedule there, the way the heads were distilled. Other samplers there drew duplicated objects
  (a second umbrella shaft), and fresh noise there cost likeness.
- **Texture** (skin, hair, fabric, grain) is drawn on the last two steps. There the node uses a
  second-order exponential step (exponential Heun), fresh noise, and a slightly lower noise level for
  the second evaluation, which brings out pores, stray hairs and fabric weave at 16-20 MP.
- Every model call is told its exact step, so H3 always uses the right distilled head.

8 model calls per image: about 30-50 s at 16-20 MP on an RTX PRO 6000 (96 GB).

## Nodes

| Node | Output | Use |
|---|---|---|
| **H3 Image KSampler** | LATENT | Drop-in replacement for KSampler with H3 Image: model, positive, latent, seed. |
| H3 Image Sampler | SAMPLER | The same sampler for `SamplerCustomAdvanced` graphs. |
| H3 Image Sigmas | SIGMAS | H3's schedule: `simple 6` or the exact stored grid. |

Advanced inputs (leave them unless you are experimenting):

| Input | Default | What it does |
|---|---|---|
| `texture_from` | 0.55 | Steps starting at or below this noise level draw texture. 0 = stock Euler throughout. |
| `eta` | 0.65 | Share of the noise replaced with fresh noise on texture steps (0.65 = 42% of the variance). |
| `detail` | 0.07 | The second evaluation of a texture step is told a noise level 7% lower. 0 = off. |
| `schedule` | simple 6 | `simple 6` gives the same layout as KSampler (euler, simple, 6) for the same seed. `exact grid` lands exactly on the distilled levels; the layout then differs a little. |

## Example workflow

`example_workflows/H3 Image - realism edit.json` shows up in ComfyUI's template browser under this pack.
It edits Picture 1, with a face close-up of it as Picture 2, at 16 MP, and has notes on every step. Its
loaders link to the official model files, so ComfyUI can offer the downloads.

## Tested

- With `texture_from` 0 the node is pixel-identical to KSampler (euler, simple, 6), both as the
  all-in-one node and through SamplerCustomAdvanced.
- Its structure steps are KSampler's own, so a seed gives KSampler's layout. In a 10-seed test where
  other samplers drew a duplicated object (a second umbrella shaft), KSampler and the stock + RES4LYF
  chain, which share these structure steps, drew none.
- Six photo edits against the stock + RES4LYF chain: the same skin, hair and texture at 100%, and
  face-match likeness 0.549 vs 0.562, within seed noise.
- Seven text and product edits at 20 MP (label text kept in new scenes; new signs and printed text):
  every word kept. At 100% the letter edges are identical to KSampler's; the texture steps add grain
  around the letters, not into them. In a 16 MP render, though, a printed t-shirt came out with a ghosted,
  misspelled line. Stock KSampler, the RES4LYF chain and the node with eta or detail at 0 draw the same
  line at that seed and size, so it comes from the model's layout, not the sampler: check text on
  clothing at 100%.

Tested with ComfyUI 0.45.3, model `minimax_h3_image_pruned_int8_convrot`.

## Licence

GPL-3.0, like ComfyUI.

Credits: MiniMax H3 Image by MiniMax, ComfyUI, and RES4LYF by ClownsharkBatwing, whose samplers this
recipe was worked out with.
