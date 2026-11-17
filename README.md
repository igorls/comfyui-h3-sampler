# H3 Image KSampler for ComfyUI

A KSampler for **MiniMax H3 Image**, tuned for photographic realism. One node does what a stock ComfyUI +
RES4LYF chain of ten nodes does, with the same skin, hair and texture at 100%. Its defaults are the
tested recipe. Plus **H3 Image Empty Picture**, which keeps text to image out of H3's crusty text-only
mode. No dependencies beyond ComfyUI.

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
  the second evaluation, which brings out pores, stray hairs and fabric weave in 16-20 MP edits.
- Every model call is told its exact step, so H3 always uses the right distilled head.

8 model calls per image on an RTX PRO 6000 (96 GB): about 30-50 s for a 16-20 MP edit, about 27 s for a
16 MP text-to-image render.

**Text to image needs a picture.** Without any picture in its conditioning, H3 Image renders in a
text-only mode that comes out crusty and over-sharpened at 100%, whatever the sampler. Any picture
switches it to its much cleaner reference mode. **H3 Image Empty Picture** does this cheaply: it puts the
vision tokens of a black 512 px picture in front of the prompt on the first two steps only, with no
reference latent, and the prompt never mentions it. It is a port of the "text with empty image" mode of
Kijai's MiniMax H3 Prompt Weight node (ComfyUI-KJNodes) and gives pixel-identical results. Put it between
MiniMax H3 Image Conditioning and the sampler; the text-to-image example does.

## Nodes

| Node | Output | Use |
|---|---|---|
| **H3 Image KSampler** | LATENT | Drop-in replacement for KSampler with H3 Image: model, positive, latent, seed. |
| H3 Image Sampler | SAMPLER | The same sampler for `SamplerCustomAdvanced` graphs. |
| H3 Image Sigmas | SIGMAS | H3's schedule: `simple 6` or the exact stored grid. |
| **H3 Image Empty Picture** | CONDITIONING | Text to image: clip and positive in, positive out, between MiniMax H3 Image Conditioning and the sampler. Keeps H3 in its clean reference mode. Leaves conditioning that already has a picture (an edit) as it is. Advanced inputs `start` 0 and `end` 0.25: the part of sampling that sees the picture. |

Advanced inputs (leave them unless you are experimenting):

| Input | Default | What it does |
|---|---|---|
| `texture_from` | 0.55 | Steps starting at or below this noise level draw texture. 0 = stock Euler throughout. |
| `eta` | 0.65 | Share of the noise replaced with fresh noise on texture steps (0.65 = 42% of the variance). |
| `detail` | 0.07 | The second evaluation of a texture step is told a noise level 7% lower. 0 = off. |
| `schedule` | simple 6 | `simple 6` gives the same layout as KSampler (euler, simple, 6) for the same seed. `exact grid` lands exactly on the distilled levels; the layout then differs a little. |

## Example workflows

Both show up in ComfyUI's template browser under this pack, with notes on every step. Their loaders link
to the official model files, so ComfyUI can offer the downloads.

- `H3 Image - realism edit.json` edits Picture 1, with a face close-up of it as Picture 2, at 16 MP.
- `H3 Image - realism text to image.json` makes a 16 MP photograph from a prompt, with H3 Image Empty
  Picture keeping H3 in its clean reference mode.

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
- Text to image, same prompt and seed at 16 MP: with H3 Image Empty Picture, fine-detail energy fell
  from 35 to 12 on a landscape and from 16 to 9 on a portrait, the range of our photo edits, and the
  crusty textures went away. Its output is pixel-identical to KJNodes' "text with empty image" mode on
  both shots. An empty black, grey or white picture wired through the conditioning node is as clean, but
  costs more: 30 s per image against 26.8 s for H3 Image Empty Picture and 24.8 s with no picture.
  Decoding the same latent tiled or whole gives the same image, so the VAE is not the cause.

Tested with ComfyUI 0.45.3, model `minimax_h3_image_pruned_int8_convrot`.

## Licence

GPL-3.0, like ComfyUI.

Credits: MiniMax H3 Image by MiniMax, ComfyUI, RES4LYF by ClownsharkBatwing, whose samplers this
recipe was worked out with, and Kijai (ComfyUI-KJNodes), whose "text with empty image" mode H3 Image
Empty Picture ports.
