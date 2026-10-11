# Design brief: visual overhaul of the Observatory page

Paste this (whole) into the design tool, together with the baseline screenshots in
`build/ui-baseline/` (regenerate with `.venv/bin/python tools/ui_shots.py`).

## Goal and audience

The Free Will Observatory is a single-page instrument that runs inside an iframe on qollab.xyz.
Goal: a cinematic but legible "observatory" look (night sky, instrument panel, warm light on cold
depths) that makes the brain graph the hero while every control and reading stays readable at a
glance. Judges score novelty and creativity first, then technical execution and documentation;
UI accessibility is a stated submission requirement. Viewers: hackathon judges and curious
visitors on desktop Chrome, Edge or Firefox; the page must also work at 360 px wide.

## Non-negotiable constraints (the platform and the tests enforce them)

- Framework: a plain HTML **body fragment** (`qollab_project/index.html`: no `<html>`, `<head>`,
  `<body>`, no `<script>`, no `on*=` attributes), **one stylesheet** `main.css` (the only CSS the
  platform loads; a Google Fonts `@import` is allowed), vanilla ES-module JavaScript in `ui/*.js`,
  three.js only through `import * as THREE from "three"`. No React, Vue, Tailwind, npm, bundlers,
  other CDNs or image files (inline SVG and CSS only). Every file under 2 MB.
- Keep every element `id`, `role`, `aria-*`, `label for`, the tablist/tabpanel structure, the
  `details`/`summary` drawers, the `aria-live` region, and the visible focus outline
  (3 px, contrast at least 3:1). Keep all visible text unchanged: the wording is reviewed for
  scientific honesty and must not be rewritten by a styling pass.
- Keep the data-to-visual mappings in `ui/scene.js`: future-sphere radius proportional to the
  cube root of its probability; branch thickness 2 + 10 p px; World-bridge opacity and thickness
  from the Connection reading; fixed seeded geometry (motion must never look like evidence);
  the previous result kept as a muted ghost; decorative particles split p0/p1; a one-second
  transition; `prefers-reduced-motion` honoured. Materials, colours, lighting, glow, lobe shape
  and typography may change freely.
- Contrast: all text at least 4.5:1 on its background, non-text UI at least 3:1 (a test computes
  this from the CSS variables); never encode meaning by colour alone (keep the shapes and labels).
- Change colours, radii and spacing through the CSS variables in `main.css` (`--fwo-bg`,
  `--fwo-surface`, `--fwo-surface-2`, `--fwo-text`, `--fwo-muted`, `--fwo-self`,
  `--fwo-self-strong`, `--fwo-world`, `--fwo-control`, `--fwo-border`, `--fwo-focus`,
  `--fwo-ghost`, `--fwo-ok-*`, `--fwo-warn-*`, `--fwo-error-*`, `--fwo-info-bg`,
  `--fwo-chart-*`, `--fwo-radius`, `--fwo-on-accent`).
- Layout order stays: persona tabs across the top; three controls at left; graph in the centre;
  future probabilities at right; the three readings and the before/after chart below; the
  explanation (factual sentence, then the persona line); the two baselines; the "How this works"
  drawer; the footer with the line "This effort is supported by Qollab & IonQ" verbatim.

## Measurable targets (starting values; adjust with taste)

Base text 16 px / 1.5; H1 2.5 rem / 1.15; section titles 1.25 rem; card padding 20 to 24 px;
corner radius 10 px; focus ring 3 px; touch targets at least 44 px; content width at most
1280 px; scene about 16:10 on desktop and at least 320 px tall on mobile; dark navy background,
teal for the Self, amber for the World, light text.

## Creative freedom

The atmosphere and identity; one display typeface plus one text typeface (Google Fonts);
the scene's look (depth, glow, materials, particle style, how the two futures and the World
bridge read); card hierarchy; the futures panel as two branches; the three readings as
instrument dials or gauges (inline SVG) with their numbers and intervals still printed; chart
styling; restrained micro-animation that switches off under reduced motion.

## Acceptance gate after every pass

```bash
.venv/bin/python -m pytest -o addopts= -q tests/test_ui_static.py tests/test_integration_fwo.py
```

```bash
.venv/bin/python tools/pack_for_qollab.py --entry js
```

```bash
.venv/bin/python tools/scrub_check.py
```

Then look at the page in stub mode: serve the repo root on 127.0.0.1 and open
`dev/index.html?auto=90|0|0&slow=0` (open futures), `?auto=90|1|0` (unresolved capacity),
`&persona=demon`, `&persona=observer`, `&how=1` (drawer), `&reduce=1`, `&nowebgl=1`,
and the same at 360 px wide.
