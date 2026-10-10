# Demo video plan (2 to 3 minutes)

The rules require a **2–3 minute** demo at a **public link that needs no sign-in**. The
outline below runs **2:45**, which leaves 15 seconds of slack under the 3:00 limit and
stays well above the 2:00 minimum. At a calm 140 words per minute, that is about 380 words
of narration. Write the script first, then record.

This effort is supported by Qollab & IonQ (show this line on screen at the start and the
end, and say it aloud once).

## Outline and shot list

`TODO(idea)` marks what changes once the idea is chosen. Until then, the CHSH reference
experiment fills every slot.

| Time | Segment | On screen | Narration (key points) |
|---|---|---|---|
| 0:00–0:15 | **Hook question** | Title card: project name, one-line question, the attribution line | TODO(idea): the question. CHSH version: "Quantum theory predicts that two qubits can be more correlated than any classical model allows. How much noise does it take to erase that, and how would you know?" |
| 0:15–0:40 | **The claim card** | The claim card in the Qollab console (or page): Claim, Assumptions, Witness | Read the claim in one breath. Name the three assumptions. "The classical bound is 2, and quantum theory predicts 2.83." Point at the verdict rule: z ≥ 3 *exceeds*, z ≤ 0 *consistent*, otherwise *inconclusive*. |
| 0:40–1:15 | **The one-job IonQ run** | Run dialog: pick the IonQ Forte simulator → Run → output: "one job", canary check passed, readout flip rates, S ± se, verdict | "IonQ allows one job per run, so everything goes in one job: the four settings plus canaries that check bit order and measure readout error." Show the mitigated vs raw value. Mention that the judges' default, the built-in simulator, gives the same structure. If the IonQ run is pre-recorded, say so. |
| 1:15–1:50 | **The noise dial crossing S = 2** | Noise dial (JS page) or the precomputed text curve: drag or scroll p₂ until S crosses 2 | "S falls in a straight line, 2√2(1 − λ). It hits 2 at λ = 1 − 1/√2, about 0.29, and our dial reproduces that to 10⁻¹⁰." Then: "With IonQ's published Forte-1 rates on our own gates, which is only an approximation of IonQ's noise, S is 2.81, and the noise would have to be about 54 times larger to reach 2." Then: "Our error bars land within one standard error 67–69% of the time; 68% is the target." |
| 1:50–2:10 | **Honesty note** | The "What this does NOT show" section of the card | "This is a simulation. It computes what quantum theory predicts under a noise model. It is not a test of nature. Both qubits live in one simulator, so the locality loophole is wide open." |
| 2:10–2:35 | **How to run it** | Qollab project page → Built-in simulator → Run; then the repo README | "Open the project, keep the built-in simulator, press Run. Everything else (tests, the sweeps, how to add your own experiment) is in the README." |
| 2:35–2:45 | **Close** | Credits card: team names, "Built with Qiskit", AI-assistance disclosure, the attribution line | "Built during the hackathon with help from an AI coding assistant. This effort is supported by Qollab & IonQ." |

TODO(idea): replace the 0:15–1:50 content with the idea's own claim card, run and dial,
and keep the CHSH material to one sentence at most.

## Recording tips

- **Rehearse against a timer** once, then record. Cut silences in editing rather than
  rushing the narration.
- **Make text readable:** record at 1920×1080 with the browser zoomed to 125–150%. Zoom
  into the claim card and the dial; judges watch on laptops.
- **Show nothing private:** use a clean browser window with no bookmarks bar, open tabs,
  account names, notifications or desktop icons in view. Never show a terminal prompt,
  window title or file path that names a person or a machine. Before uploading, watch the
  whole video once just to check this.
- **IonQ run:** record it once, when it is first made (see [SUBMIT.md](SUBMIT.md)), so the
  video never depends on a remote job finishing during the recording. Say on screen that
  the clip is a recording.
- **Audio:** use a headset or external microphone in a quiet room, and keep a consistent
  distance. Background music, if any, stays at least 20 dB below the voice.
- **Export** as MP4 (H.264, AAC), then upload with **public or unlisted** visibility at a
  link that plays **without signing in**. Test the link in a private browser window
  before submitting.

## Accessibility

- **Captions:** provide accurate captions, not unreviewed automatic ones. Upload a caption
  file (SRT/VTT) or burn the captions in. Read through the captions for math terms
  ("S equals two root two", "lambda star").
- **Transcript:** paste the final narration below, so the video's content also exists as
  text.
- **Describe the visuals in words:** say the numbers you show ("S is 2.85, plus or minus
  0.04"), and never rely on color ("the red line"). Keep any color a viewer must
  distinguish high in contrast.
- **No flashing:** avoid rapid cuts or flashing content (no more than three flashes per
  second).

## Transcript

TODO(team): paste the final narration here after recording.
