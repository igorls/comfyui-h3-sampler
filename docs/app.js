(() => {
  const liveStatus = document.getElementById("liveStatus");
  function announce(msg) {
    if (!liveStatus || !msg) return;
    liveStatus.textContent = "";
    requestAnimationFrame(() => {
      liveStatus.textContent = msg;
    });
  }

  /* ------------------------------------------------------------- Shared Optical Comparison Catalog */
  const COMPARISONS = {
    p2_cheek: {
      title: "Kitchen Portrait — Skin Pores & Curls",
      beforeLabel: "Full-band (6 calls)",
      afterLabel: "Spectral 6 (6 calls)",
      beforeImg: "assets/p2_cheek_fullband.jpg",
      afterImg: "assets/p2_cheek_spec6.jpg",
      caption:
        "Kitchen Portrait (960×640 native crop from 16 MP, seed 5000). Full-band re-noising irons cheeks smooth; Spectral 6 preserves pores, lashes and curls in the same 6 calls.",
      metrics: "6 calls · Mean edit ID: 0.525 vs 0.508 (v1.1)",
      dims: "960 × 640 px · 1:1 crop from 3360×5024",
      views: [
        {
          label: "Full-band re-noise (6 calls)",
          src: "assets/p2_cheek_fullband.jpg",
          note: "Full-band mid-step re-noising wipes fine pores and baby curls into waxy plastic. (←/→ or Space to blink)",
        },
        {
          label: "Spectral 6 (6 calls)",
          src: "assets/p2_cheek_spec6.jpg",
          note: "H3 Realism Spectral 6 preserves pores, lashes and curls while locking low-frequency layout. (←/→ or Space to blink)",
        },
      ],
    },
    p2_shirt: {
      title: "Kitchen Portrait — Linen Weave & Stripes",
      beforeLabel: "Full-band (6 calls)",
      afterLabel: "Spectral 6 (6 calls)",
      beforeImg: "assets/p2_shirt_fullband.jpg",
      afterImg: "assets/p2_shirt_spec6.jpg",
      caption:
        "Kitchen Portrait linen & cotton stripes (960×640 native crop, seed 5000). Frequency-split re-noising keeps woven threads, seam stitching and fabric slub instead of blurring them flat.",
      metrics: "Low-freq Euler lock (<0.25) · Exact N(0, I) noise",
      dims: "960 × 640 px · 1:1 crop from 3360×5024",
      views: [
        {
          label: "Full-band re-noise (6 calls)",
          src: "assets/p2_shirt_fullband.jpg",
          note: "Full-band re-noising flattens striped knit and apron linen into soft vector-like bands. (←/→ or Space to blink)",
        },
        {
          label: "Spectral 6 (6 calls)",
          src: "assets/p2_shirt_spec6.jpg",
          note: "H3 Realism Spectral 6 preserves cotton knit texture, apron weave and stitched seams. (←/→ or Space to blink)",
        },
      ],
    },
    p6_hands: {
      title: "Snowy Forest — Bare Hands & Red Wool",
      beforeLabel: "Full-band (gloves)",
      afterLabel: "Spectral 6 (bare hands)",
      beforeImg: "assets/p6_hands_fullband.jpg",
      afterImg: "assets/p6_hands_spec6.jpg",
      caption:
        "Snowy Forest edit (960×640 native crop from 16 MP, seed 5000). Full-band re-noising mutated bare hands into leather gloves; Spectral 6 locks bare hands, axe wood grain and snow on wool.",
      metrics: "Laplacian RMS: 5.45 (full-band) vs 6.26 (Spectral 6)",
      dims: "960 × 640 px · 1:1 crop from 5024×3360",
      views: [
        {
          label: "Full-band re-noise (mutated)",
          src: "assets/p6_hands_fullband.jpg",
          note: "Re-noising low frequencies replaced the subject's bare hands with brown leather gloves. (←/→ or Space to blink)",
        },
        {
          label: "Spectral 6 (bare hands locked)",
          src: "assets/p6_hands_spec6.jpg",
          note: "Low-frequency Euler lock keeps bare hands, fingers, axe handle grain and red wool intact. (←/→ or Space to blink)",
        },
      ],
    },
    p4_face: {
      title: "Piano Portrait — Face & Silver Hair",
      dims: "960 × 640 px · 1:1 crop from 3360×5024 (seed 5000)",
      views: [
        {
          label: "Full-band re-noise (6 calls)",
          src: "assets/p4_face_fullband.jpg",
          note: "Full-band re-noising softens fine cheek texture and lowers facial identity (0.635 ID). (←/→ or Space to blink)",
        },
        {
          label: "Spectral 6 (0.658 ID)",
          src: "assets/p4_face_spec6.jpg",
          note: "H3 Realism Spectral 6 achieves the highest InsightFace ID (0.658 vs 0.621 in v1.1) with crisp silver hair strands and natural pores. (←/→ or Space to blink)",
        },
      ],
    },
    elder_beard: {
      title: "Elder Portrait — Beard Hairs & Skin (T2I)",
      dims: "960 × 640 px · 1:1 crop from 3360×5024 (seed 5000)",
      views: [
        {
          label: "Plain T2I (crusty)",
          src: "assets/elder_beard_plain.jpg",
          note: "Plain text-to-image without Empty Picture renders harsh, over-sharpened crust (Lap RMS 13.68). (←/→ or 1–3 to blink)",
        },
        {
          label: "Empty Picture + Spectral 8",
          src: "assets/elder_beard_v2.jpg",
          note: "Native Empty Picture + Spectral 8 yields crisp individual white hairs and organic skin (Lap RMS 7.93). (←/→ or 1–3 to blink)",
        },
        {
          label: "Full-band + steering",
          src: "assets/elder_beard_fullband.jpg",
          note: "Rank-1 steering + full-band re-noising softens beard strands into a fuzzy wash with fine stipple (hf/mid 0.158). (←/→ or 1–3 to blink)",
        },
      ],
    },
    lake_pines: {
      title: "Misty Mountain Lake — Pines & Atmosphere (T2I)",
      dims: "960 × 640 px · 1:1 crop from 5024×3360 (seed 5002)",
      views: [
        {
          label: "Plain T2I (crusty)",
          src: "assets/lake_1to1_plain.jpg",
          note: "Plain T2I produces harsh speckled pine needles and brittle micro-contrast (Lap RMS 34.77, hf/mid 0.207). (←/→ or Space to blink)",
        },
        {
          label: "H3 Realism Empty Picture",
          src: "assets/lake_1to1_v2.jpg",
          note: "Prepending a black 512 px picture's vision tokens on steps 0–1 restores clean optical depth (Lap RMS 11.80, hf/mid 0.091). (←/→ or Space to blink)",
        },
      ],
    },
  };

  /* ------------------------------------------------------------- 1:1 Pixel-Aligned Hero Loupe */
  const viewport = document.getElementById("compareViewport");
  const beforeImg = document.getElementById("compareBefore");
  const afterImg = document.getElementById("compareAfter");
  const tagBefore = document.getElementById("tagBefore");
  const tagAfter = document.getElementById("tagAfter");
  const captionEl = document.getElementById("loupeCaption");
  const metricsEl = document.getElementById("loupeMetrics");
  const knob = document.getElementById("compareKnob");
  const loupeZoomBtn = document.getElementById("loupeZoomBtn");
  const presetBtns = Array.from(document.querySelectorAll("[data-preset]"));

  let splitPct = 50;
  let currentPreset = "p2_cheek";

  function setSplit(pct) {
    splitPct = Math.max(4, Math.min(96, pct));
    viewport.style.setProperty("--split", `${splitPct.toFixed(2)}%`);
    knob.setAttribute("aria-valuenow", String(Math.round(splitPct)));
  }

  function loadPreset(key, shouldAnnounce) {
    const p = COMPARISONS[key];
    if (!p || !p.beforeImg) return;
    currentPreset = key;
    beforeImg.src = p.beforeImg;
    beforeImg.alt = `${p.title}: ${p.beforeLabel}`;
    afterImg.src = p.afterImg;
    afterImg.alt = `${p.title}: ${p.afterLabel}`;
    tagBefore.textContent = p.beforeLabel;
    tagAfter.textContent = p.afterLabel;
    captionEl.textContent = p.caption;
    metricsEl.textContent = p.metrics;
    presetBtns.forEach((b) => {
      b.setAttribute("aria-pressed", String(b.dataset.preset === key));
    });
    if (shouldAnnounce) {
      announce(`Loaded comparison: ${p.title}`);
    }
  }

  if (viewport && knob) {
    let dragging = false;

    const updateFromClientX = (clientX) => {
      const rect = viewport.getBoundingClientRect();
      if (rect.width <= 0) return;
      setSplit(((clientX - rect.left) / rect.width) * 100);
    };

    viewport.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      dragging = true;
      if (viewport.setPointerCapture) {
        viewport.setPointerCapture(e.pointerId);
      }
      updateFromClientX(e.clientX);
    });

    viewport.addEventListener("pointermove", (e) => {
      if (!dragging) return;
      updateFromClientX(e.clientX);
    });

    const stopDrag = () => {
      dragging = false;
    };
    viewport.addEventListener("pointerup", stopDrag);
    viewport.addEventListener("pointercancel", stopDrag);

    knob.addEventListener("keydown", (e) => {
      const step = e.shiftKey ? 10 : 3;
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        setSplit(splitPct - step);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        setSplit(splitPct + step);
      } else if (e.key === "Home") {
        e.preventDefault();
        setSplit(4);
      } else if (e.key === "End") {
        e.preventDefault();
        setSplit(96);
      }
    });

    presetBtns.forEach((btn) => {
      btn.addEventListener("click", () => loadPreset(btn.dataset.preset, true));
    });

    setSplit(50);
    loadPreset("p2_cheek", false);
  }

  /* ------------------------------------------------------------- True 1:1 Native-Pixel Lightbox */
  const lightbox = document.getElementById("lightbox");
  const lightboxPanel = document.getElementById("lightboxPanel");
  const lightboxTitle = document.getElementById("lightboxTitle");
  const lightboxSub = document.getElementById("lightboxSub");
  const lightboxTabs = document.getElementById("lightboxTabs");
  const lightboxScaleBtn = document.getElementById("lightboxScaleBtn");
  const lightboxCloseBtn = document.getElementById("lightboxCloseBtn");
  const lightboxStage = document.getElementById("lightboxStage");
  const lightboxImg = document.getElementById("lightboxImg");
  const lightboxNote = document.getElementById("lightboxNote");
  const lightboxDims = document.getElementById("lightboxDims");

  const backgroundRegions = [
    document.querySelector("header"),
    document.querySelector("main"),
    document.querySelector("footer"),
  ].filter(Boolean);

  let lastTriggerEl = null;
  let activeLightboxItem = null;
  let activeViewIdx = 0;
  let nativeScale = true;

  function centerLightboxScroll() {
    requestAnimationFrame(() => {
      if (!lightboxStage) return;
      const maxX = Math.max(0, lightboxStage.scrollWidth - lightboxStage.clientWidth);
      const maxY = Math.max(0, lightboxStage.scrollHeight - lightboxStage.clientHeight);
      lightboxStage.scrollLeft = Math.round(maxX / 2);
      lightboxStage.scrollTop = Math.round(maxY / 2);
    });
  }

  function setLightboxScale(isNative) {
    nativeScale = isNative;
    lightboxStage.classList.toggle("mode-native", isNative);
    lightboxStage.classList.toggle("mode-fit", !isNative);
    lightboxScaleBtn.setAttribute("aria-pressed", String(isNative));
    lightboxScaleBtn.textContent = isNative ? "1:1 Native (100%)" : "Fit to Screen (Zoom 1:1)";
    if (isNative) {
      centerLightboxScroll();
    }
  }

  function selectLightboxView(index, shouldAnnounce) {
    if (!activeLightboxItem) return;
    const len = activeLightboxItem.views.length;
    activeViewIdx = ((index % len) + len) % len;
    const view = activeLightboxItem.views[activeViewIdx];
    lightboxImg.src = view.src;
    lightboxImg.alt = `${activeLightboxItem.title} — ${view.label}`;
    lightboxNote.textContent = view.note;
    Array.from(lightboxTabs.children).forEach((btn, i) => {
      btn.setAttribute("aria-pressed", String(i === activeViewIdx));
    });
    if (shouldAnnounce) {
      announce(`Viewing ${view.label}`);
    }
  }

  function getFocusableInLightbox() {
    if (!lightboxPanel) return [];
    return Array.from(
      lightboxPanel.querySelectorAll(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )
    );
  }

  function openLightbox(key, initialViewIndex, triggerEl) {
    const item = COMPARISONS[key];
    if (!item || !lightbox) return;
    lastTriggerEl = triggerEl || document.activeElement;
    activeLightboxItem = item;

    lightboxTitle.textContent = item.title;
    lightboxSub.textContent = "True 100% source pixels · ←/→ or Space to blink variants";
    lightboxDims.textContent = item.dims;

    lightboxTabs.innerHTML = "";
    item.views.forEach((v, idx) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "pill";
      btn.textContent = v.label;
      btn.setAttribute("aria-pressed", "false");
      btn.addEventListener("click", () => selectLightboxView(idx, true));
      lightboxTabs.appendChild(btn);
    });

    const startIdx =
      typeof initialViewIndex === "number" && initialViewIndex >= 0 && initialViewIndex < item.views.length
        ? initialViewIndex
        : item.views.length - 1;

    lightbox.hidden = false;
    document.body.classList.add("modal-open");
    backgroundRegions.forEach((el) => {
      el.inert = true;
    });

    // On narrow phone viewports, open cleanly fitted to screen so the subject is centered immediately,
    // with one-tap "Fit to Screen (Zoom 1:1)" centered on the subject.
    const preferNative = window.innerWidth >= 768;
    setLightboxScale(preferNative);
    selectLightboxView(startIdx, false);
    if (preferNative) {
      centerLightboxScroll();
    }

    lightboxCloseBtn.focus();
    announce(`Opened 1:1 inspector: ${item.title}`);
  }

  function closeLightbox() {
    if (!lightbox || lightbox.hidden) return;
    lightbox.hidden = true;
    document.body.classList.remove("modal-open");
    backgroundRegions.forEach((el) => {
      el.inert = false;
    });
    if (lastTriggerEl && typeof lastTriggerEl.focus === "function") {
      lastTriggerEl.focus();
    }
    announce("Closed 1:1 inspector");
  }

  if (lightbox) {
    if (loupeZoomBtn) {
      loupeZoomBtn.addEventListener("click", () => openLightbox(currentPreset, 1, loupeZoomBtn));
    }

    document.querySelectorAll("[data-lightbox]").forEach((trigger) => {
      trigger.addEventListener("click", () => {
        const key = trigger.dataset.lightbox;
        const initRaw = trigger.dataset.initialView;
        const initIdx = initRaw !== undefined ? parseInt(initRaw, 10) : 1;
        openLightbox(key, initIdx, trigger);
      });
    });

    lightboxScaleBtn.addEventListener("click", () => {
      setLightboxScale(!nativeScale);
      announce(nativeScale ? "Switched to 1:1 native 100% scale" : "Switched to fit to screen");
    });

    lightbox.querySelectorAll("[data-lightbox-close]").forEach((el) => {
      el.addEventListener("click", closeLightbox);
    });

    document.addEventListener("keydown", (e) => {
      if (lightbox.hidden) return;

      if (e.key === "Escape") {
        e.preventDefault();
        closeLightbox();
        return;
      }

      if (e.key === "Tab") {
        const focusables = getFocusableInLightbox();
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
        return;
      }

      if (e.key === "ArrowRight") {
        e.preventDefault();
        selectLightboxView(activeViewIdx + 1, true);
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        selectLightboxView(activeViewIdx - 1, true);
      } else if (e.key === " " && document.activeElement !== lightboxCloseBtn && document.activeElement !== lightboxScaleBtn) {
        e.preventDefault();
        selectLightboxView(activeViewIdx + 1, true);
      } else if (e.key >= "1" && e.key <= "9" && activeLightboxItem) {
        const idx = parseInt(e.key, 10) - 1;
        if (idx < activeLightboxItem.views.length) {
          e.preventDefault();
          selectLightboxView(idx, true);
        }
      }
    });
  }

  /* ------------------------------------------------------------- Copy Command Buttons */
  document.querySelectorAll("[data-copy-target]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const target = document.getElementById(btn.dataset.copyTarget);
      if (!target) return;
      const text = target.textContent.trim();
      const orig = btn.dataset.origLabel || btn.textContent;
      btn.dataset.origLabel = orig;

      try {
        if (!navigator.clipboard || !navigator.clipboard.writeText) {
          throw new Error("Clipboard API unavailable");
        }
        await navigator.clipboard.writeText(text);
        btn.textContent = "Copied";
        btn.dataset.copied = "true";
        announce("Command copied to clipboard");
        setTimeout(() => {
          btn.textContent = orig;
          delete btn.dataset.copied;
        }, 1600);
      } catch {
        const range = document.createRange();
        range.selectNodeContents(target);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        btn.textContent = "Selected — Ctrl+C";
        announce("Command selected; press Control C to copy");
        setTimeout(() => {
          btn.textContent = orig;
        }, 2200);
      }
    });
  });

  /* ------------------------------------------------------------- 2D FFT Spectral Visualizer + Presets */
  const canvas = document.getElementById("fftCanvas");
  const cutoffInput = document.getElementById("cutoffSlider");
  const etaInput = document.getElementById("etaSlider");
  const cutoffOut = document.getElementById("cutoffOut");
  const etaOut = document.getElementById("etaOut");
  const lockShareOut = document.getElementById("lockShareOut");
  const fftModeLabel = document.getElementById("fftModeLabel");
  const fftPlanOut = document.getElementById("fftPlanOut");
  const fftResetBtn = document.getElementById("fftResetBtn");
  const scheduleBtns = Array.from(document.querySelectorAll("[data-fft-preset]"));

  let fftRafId = 0;

  function setFFTModeText(label, planText) {
    if (fftModeLabel) {
      fftModeLabel.innerHTML = "";
      const prefix = document.createTextNode("Active preset: ");
      const strong = document.createElement("strong");
      strong.textContent = label;
      fftModeLabel.appendChild(prefix);
      fftModeLabel.appendChild(strong);
    }
    if (fftPlanOut && planText) {
      fftPlanOut.textContent = planText;
    }
  }

  function drawFFT() {
    fftRafId = 0;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const size = canvas.width;
    const img = ctx.createImageData(size, size);
    const data = img.data;

    const cutoff = parseFloat(cutoffInput.value);
    const eta = parseFloat(etaInput.value);
    const width = 0.2;

    cutoffOut.textContent = cutoff.toFixed(2);
    etaOut.textContent = eta.toFixed(2);

    const half = size / 2;
    let lockedCount = 0;
    let totalCount = 0;

    for (let y = 0; y < size; y++) {
      const dy = (y - half) / half;
      for (let x = 0; x < size; x++) {
        const dx = (x - half) / half;
        const r = Math.min(1, Math.sqrt((dx * dx + dy * dy) * 0.5));
        const t = Math.max(0, Math.min(1, (r - cutoff) / width));
        const hp = 0.5 - 0.5 * Math.cos(Math.PI * t);
        const etaF = eta * hp;
        const keepF = Math.sqrt(Math.max(0, 1 - etaF * etaF));

        if (etaF < 0.15) lockedCount++;
        totalCount++;

        const hash = Math.sin(x * 12.9898 + y * 78.233) * 43758.5453;
        const grain = (hash - Math.floor(hash)) * 0.16 + 0.84;

        const wFresh = etaF * etaF;
        const rCol = (205 * (1 - wFresh) + 216 * wFresh) * (0.28 + 0.62 * (keepF * 0.55 + etaF * 0.65)) * grain;
        const gCol = (200 * (1 - wFresh) + 157 * wFresh) * (0.28 + 0.62 * (keepF * 0.55 + etaF * 0.65)) * grain;
        const bCol = (190 * (1 - wFresh) + 78 * wFresh) * (0.28 + 0.62 * (keepF * 0.55 + etaF * 0.65)) * grain;

        const idx = (y * size + x) * 4;
        data[idx] = Math.min(255, Math.max(0, rCol));
        data[idx + 1] = Math.min(255, Math.max(0, gCol));
        data[idx + 2] = Math.min(255, Math.max(0, bCol));
        data[idx + 3] = 255;
      }
    }

    ctx.putImageData(img, 0, 0);

    ctx.save();
    ctx.strokeStyle = "rgba(240, 237, 230, 0.22)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(half, 0);
    ctx.lineTo(half, size);
    ctx.moveTo(0, half);
    ctx.lineTo(size, half);
    ctx.stroke();

    const rCutPx = cutoff * Math.SQRT2 * half;
    const rHiPx = Math.min(1, cutoff + width) * Math.SQRT2 * half;

    ctx.strokeStyle = "#f0ede6";
    ctx.setLineDash([4, 3]);
    ctx.beginPath();
    ctx.arc(half, half, rCutPx, 0, Math.PI * 2);
    ctx.stroke();

    ctx.strokeStyle = "#d89d4e";
    ctx.setLineDash([2, 3]);
    ctx.beginPath();
    ctx.arc(half, half, rHiPx, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();

    if (lockShareOut) {
      const pct = Math.round((lockedCount / totalCount) * 100);
      lockShareOut.textContent = `${pct}% low-freq locked`;
    }
  }

  function scheduleDrawFFT() {
    if (fftRafId) return;
    fftRafId = requestAnimationFrame(drawFFT);
  }

  function applySchedulePreset(btn, shouldAnnounce) {
    if (!btn || !cutoffInput || !etaInput) return;
    cutoffInput.value = btn.dataset.cutoff;
    etaInput.value = btn.dataset.eta;
    scheduleBtns.forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
    setFFTModeText(btn.dataset.label || "Custom", btn.dataset.plan || "");
    drawFFT();
    if (shouldAnnounce) {
      announce(`FFT preset: ${btn.dataset.label}. ${btn.dataset.plan || ""}`);
    }
  }

  if (canvas && cutoffInput && etaInput) {
    const onManualInput = () => {
      scheduleBtns.forEach((b) => b.setAttribute("aria-pressed", "false"));
      const c = parseFloat(cutoffInput.value).toFixed(2);
      const e = parseFloat(etaInput.value).toFixed(2);
      setFFTModeText(`Custom (${c} / ${e})`, `Custom FFT split · cutoff ${c} · high-freq share ${e}`);
      scheduleDrawFFT();
    };

    cutoffInput.addEventListener("input", onManualInput);
    etaInput.addEventListener("input", onManualInput);

    scheduleBtns.forEach((btn) => {
      btn.addEventListener("click", () => applySchedulePreset(btn, true));
    });

    if (fftResetBtn) {
      fftResetBtn.addEventListener("click", () => {
        const defBtn = scheduleBtns.find((b) => b.dataset.fftPreset === "spectral6");
        if (defBtn) {
          applySchedulePreset(defBtn, true);
        } else {
          cutoffInput.value = "0.25";
          etaInput.value = "0.85";
          setFFTModeText("Spectral 6 (default)", "6 calls · Steps 0–1 Euler · Steps 2–4 FFT · Step 5 Euler");
          drawFFT();
        }
      });
    }

    drawFFT();
  }

  /* ------------------------------------------------------------- Active-Section Nav Scroll-Spy */
  const siteNav = document.querySelector(".site-nav");
  const navLinks = Array.from(document.querySelectorAll(".site-nav a[href^='#']"));
  const observedSections = navLinks
    .map((a) => document.querySelector(a.getAttribute("href")))
    .filter(Boolean);

  if ("IntersectionObserver" in window && observedSections.length > 0) {
    const setActiveLink = (id) => {
      navLinks.forEach((a) => {
        const isCurrent = a.getAttribute("href") === `#${id}`;
        if (isCurrent) {
          a.setAttribute("aria-current", "location");
          if (siteNav && siteNav.scrollWidth > siteNav.clientWidth && a.scrollIntoView) {
            a.scrollIntoView({ inline: "nearest", block: "nearest", behavior: "smooth" });
          }
        } else {
          a.removeAttribute("aria-current");
        }
      });
    };

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible.length > 0) {
          setActiveLink(visible[0].target.id);
        }
      },
      { rootMargin: "-22% 0px -65% 0px", threshold: 0 }
    );

    observedSections.forEach((sec) => observer.observe(sec));
  }
})();
