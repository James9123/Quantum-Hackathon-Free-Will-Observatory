# Design brief: visual overhaul of the Observatory page

*Part of the [documentation set](README.md).*

Paste this (whole) into the design tool, together with the baseline screenshots in
`build/ui-baseline/` (regenerate with `.venv/bin/python tools/ui_shots.py`).

## Inspiration: Laplace's Demon and the limits of calculation

One of the Observatory's three personas is **Laplace's Demon**, and the name is not
decoration. In 1814, Pierre-Simon Laplace opened his *Essai philosophique sur les
probabilités* with a thought experiment: an intellect that knew, at a single instant, the
precise position and momentum of every particle in the universe could — given Newtonian
mechanics and enough calculating power — derive the entire past and future with certainty.
"Nothing would be uncertain, and the future, as the past, would be present to its eyes."
This "demon" became the canonical statement of classical, mechanistic determinism: chance is
not a fact about the world, only a name for our ignorance of its exact state.

Bell's theorem and its experimental tests (the CHSH inequality this team's toolkit is built
around — `qk_bounds.py`, validated on the CHSH reference project in
[reference/chsh/](../reference/chsh/)) are the modern, empirical answer to that picture. Any
**local hidden-variable theory** — any model in which a system's measurement outcomes are
fixed in advance by some underlying variable, local and non-conspiratorial, exactly the kind
of hidden deterministic substrate a Laplace's-Demon-style account of quantum randomness would
need — predicts CHSH correlations bounded by **S ≤ 2**. Quantum mechanics predicts, and
decades of experiments confirm, violations up to the **Tsirelson bound S = 2√2 ≈ 2.828**. A
demon that merely lacked our information, but was otherwise playing by local, realist rules,
could not reproduce what quantum systems actually do.

The Observatory borrows this history rather than re-running it: the live page does not
perform a CHSH test (see [claims.md](claims.md), Card C — Connection is explicitly *not* an
entanglement certification), but its Demon persona dramatizes the same tension in miniature.
The Demon computes an exact forecast from the quantum state before any shots are taken —
Laplace's "present to its eyes" — yet what it computes is a *probability*, not a certainty,
and the project's central result (the same 50/50 outcome is high-capacity under one setting
and zero-capacity under another, [README § The question](../README.md#the-question)) is a
question Laplace's framework has no room for: knowing the odds perfectly is not the same as
them being fixed, and whether an input can *move* those odds is a different question from
whether the Demon can predict them. The Self, Demon and Observer personas stage that
three-way disagreement — about the same job's counts — as a dialogue rather than an equation.

**Where the honesty rule still applies.** Bell tests rule out *local hidden-variable*
determinism specifically; they say nothing about superdeterminism, non-local hidden-variable
accounts (Bohmian mechanics survives them by construction), or determinism in general, and
nothing at all about free will as philosophers debate it. The Observatory's fiction goes
further than the physics licenses — that is the point of calling it a fiction. Keep the
Laplace's Demon framing here, in the narrative brief; [claims.md](claims.md) and
[model.md](model.md) stay scoped to the project's own measured, falsifiable statements about
Capacity, Openness and Connection, and should not be read as a Bell-inequality claim.

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
