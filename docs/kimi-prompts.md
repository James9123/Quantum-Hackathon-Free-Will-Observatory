# Kimi Design prompts for the visual overhaul

*Part of the [documentation set](README.md). This is a process record of the prompts used
with an AI design tool; [design-brief.md](design-brief.md) is the actual specification.*

Paste prompt 1 with the current-state screenshots and the team build guide attached. Prompts 2
and 3 follow once a direction is chosen. The repo-side rules live in `docs/design-brief.md`.

## Prompt 1: four directions, then compare

```
You are redesigning the look of "The Free Will Observatory", a single-page web instrument for a
quantum-computing hackathon (attached: screenshots of the current page on the real platform;
the team build guide PDF, see pages 3 and 10 for the intended scene and layout). Judges score
novelty and creativity first, then technical execution and documentation. Accessibility is a
submission requirement.

Task: produce FOUR deliberately different design directions, then compare them. Do not
converge early. For each direction give:
1. A full-page desktop mockup, 1280 px wide, in the "after a run" state with these real values:
   Future 1 = 48.5%, Future 0 = 51.5%, Capacity 1.00 (95% interval 0.91 to 1.00), Openness
   0.999 bits, Connection 0.000 bits, factual sentence and persona line as in the screenshots.
2. A mobile mockup, 390 px wide, of the top half (tabs, controls, scene, two futures).
3. A one-paragraph rationale, and a token sheet: background, surface, text, muted text, Self
   accent, World accent, focus ring, border, error/warn/ok colours as hex, with the contrast
   ratio of every text colour on its background; type pairing with sizes; corner radius;
   spacing scale.

Make the four directions differ on every axis:
- A "Night observatory": deep navy with starfield depth, warm brass/amber instrument accents,
  a serif display face; cinematic.
- B "Instrument console": flat dark slate, monospaced readouts, readings as gauges and dials,
  thin grid lines; technical and calm.
- C "Luminous anatomy": near-black, the brain graph as a glowing translucent organism, soft
  gradients, large editorial type; art-piece feel.
- D "Blueprint, light": an off-white or blueprint-blue LIGHT theme with ink lines and
  diagrammatic marks; the control case against dark.
Vary the scene treatment too (glow vs wireframe vs flat shaded) and the density (airy vs dense).

Keep in every direction (non-negotiable):
- Section order: persona tabs across the top; three slider controls at left; the scene in the
  centre; the two future probabilities at right; the three readings and the before/after chart
  below; the explanation (one factual sentence, then the persona line); two baseline cards;
  the "How this works" drawer; the footer line "This effort is supported by Qollab & IonQ".
- All text exactly as in the screenshots. Do not invent sentences or claims; where you need
  text that is not in the screenshots, draw a grey placeholder block.
- The data-driven elements and what drives them: two future spheres whose radius follows the
  cube root of each probability; branch thickness 2 + 10 p px; a World bridge whose opacity
  and thickness follow the Connection reading; the previous result shown as a muted ghost;
  the brain graph itself is decorative with fixed geometry (motion must never look like data).
- Self and World must stay distinguishable by label and shape, not colour alone; all text at
  least 4.5:1 contrast on its background; a visible 3 px focus ring; touch targets 44 px;
  everything legible at 390 px wide.
- Buildable in plain HTML + one CSS file + vanilla JavaScript + three.js: gradients, CSS and
  inline SVG only; no photographic textures, no image assets, Google Fonts allowed.

Then compare the four in one table scored 1 to 5 on: novelty, legibility at a glance,
accessibility (contrast, colour-independence), faithfulness to the data mappings, and
feasibility in plain CSS + three.js. Name the strongest direction and the single best idea
worth borrowing from each of the other three. The team chooses after that.
```

## Prompt 2: refine the chosen direction into all states

```
Take direction <X> with these borrowed ideas: <list>. Keep its token sheet fixed and produce the
full state set at 1280 px wide: idle (no run yet); after a run (Act 1 values above); the
unresolved run (Future 1 = 52.5%, Capacity 0.03, interval 0.00 to 0.12, the status line
"No resolved influence at this shot count.", Connection 0.999 bits); the Demon tab with its
forecast card; the "How this works" drawer open (four 2x2 count tables, job details); a failed
run; and 390 px mobile versions of idle and after-run. Same layout order and text rules as
before. Mark anything that changed from prompt 1's mockup.
```

## Prompt 3: the implementation spec for the code pass

```
Write the implementation spec for direction <X> as plain text: CSS custom properties (name,
hex, where used, contrast ratio against its background); type scale (family, size, line
height, weight per role); spacing and radius scales; per-component rules (tabs, slider field,
Run button and its disabled/locked/waiting states, scene frame and labels, future cards,
reading cards, chart, explanation, baselines, drawer, footer); scene material and lighting
notes for three.js (sphere, branch, bridge, ghost, particles, lobes); motion rules and their
reduced-motion fallback; and a checklist of what must not change (ids, aria, text, mappings).
```
