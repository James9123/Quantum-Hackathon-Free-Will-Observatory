# Demo video plan (2 to 3 minutes)

The rules require a **2–3 minute** demo at a **public link that needs no sign-in**. The
outline below runs **2:45**, which leaves 15 seconds under the 3:00 limit and stays well
above the 2:00 minimum. At a calm 140 words per minute that is about 380 words of
narration. Write the script first, then record.

This effort is supported by Qollab & IonQ (show this line on screen at the start and the
end, and say it aloud once).

**Three acts, one page.** Each live experiment produces the next visual change; the
narration is short and the lines in quotation marks are the team's own, from the build
guide. Settings: Self persona, perspective β = 0 throughout the acts, 1,024 shots per probe,
the built-in simulator.

## Outline and shot list

| Time | Segment | On screen | Narration (key points) |
|---|---|---|---|
| 0:00–0:15 | **Hook** | Title card: *The Free Will Observatory*, "a fictional instrument for exploring the capacity to reshape possible futures", the attribution line | "Is an uncertain future the same thing as a free one? This instrument gives the question a precise rule and lets you test it on a two-qubit Self." |
| 0:15–0:35 | **The scene** | The brain-shaped graph, the two future branches, the World bridge, the three persona tabs, the three sliders (Intention, World coupling, Perspective) | "One fictional Self with two possible futures. An intention is a quantum phase, the World is a coupled second qubit, a perspective is a measurement choice. Every number comes from one fresh simulator job of four small Qiskit circuits." |
| 0:35–1:05 | **Act 1: Possible futures** | Self mode, w = 0, φ = π/2, β = 0. Press *Run experiment*; the job runs; the branches settle near 50/50; readings: Capacity 1.00 with its interval, Openness ≈ 1 bit, Connection ≈ 0 | "The future is open: about half of the outcomes go each way. Opposite intentions can still move the odds across their full range." Point at the Capacity interval: "two extra probes, opposite intentions, same job." |
| 1:05–1:30 | **Act 2: Intention** | Keep w = 0 and β = 0; set φ = π; rerun. The previous run stays as a ghost; Future 1 takes everything; Openness falls to ≈ 0; Capacity still 1.00 | "The outcome becomes predictable because this intention strongly directs it. Predictability and capacity can coexist." |
| 1:30–2:00 | **Act 3: Constraint** | Set w = 1 and φ = π/2; rerun. Branches back near 50/50; the World bridge brightens (Connection ≈ 1 bit); Capacity interval includes zero; the page says *No resolved influence at this shot count* | "The outcome is uncertain again, but these intention controls no longer reshape its odds. In our model, uncertainty alone is not freedom." Then: "The information went into the World: the bridge reads one bit." |
| 2:00–2:15 | **The Demon and the Observer** | Switch to Laplace's Demon: the forecast beside the sampled values and the two baselines (fixed output; fair coin). Switch to The Observer: change β, rerun (pre-recorded if slow) | "The Demon knows the probability law and predicted every number before the job returned. The Observer asks a different question of the same state: the perspective changes the observable, and Capacity stays comparable because its probes share the readout." |
| 2:15–2:35 | **Honesty, and how to run it** | The explanation drawer's honesty copy; then Qollab's Run dialog with the built-in simulator; the *How this works* drawer with the circuit and counts | "The measurements are real outputs of the simulator; the Self and its philosophical meaning are our artistic construction. A simulator computes what quantum theory predicts; it does not test nature, and a classical switch would score the same Capacity: this is a model, not proof of agency. Open the project on Qollab, keep the built-in simulator, press Run. On IonQ's simulator it is one job per run, and the four probes travel in that one job." |
| 2:35–2:45 | **Close** | Credits card: team names, "Built with Qiskit", AI-assistance disclosure, the attribution line | "Built during the hackathon with help from an AI coding assistant. This effort is supported by Qollab & IonQ." |

Allow time for real jobs. Under CPython one run on the built-in simulator takes 0.03–0.04 s
(measured); in the browser and on IonQ's simulator the wall time is unmeasured until the
judge run and the IonQ run (TODO(captain): note both from the `wall_s` field, SUBMIT.md
§5–6) and the recording should not promise a duration before then. If a run is
pre-recorded, say so on screen.

## Expected readings per act

Ideal values from the closed form, and one seeded local example (Qiskit `BasicSimulator`,
`seed_simulator=11`, 1,024 shots per probe, measured with this repository's code; the live
samples will differ by shot noise):

| Act | Settings | P(Self = 1) ideal / example | Capacity ideal / example | Openness | Connection |
|---|---|---|---|---|---|
| 1 | w = 0, φ = π/2, β = 0 | 0.5 / 0.485 | 1.0 / **1.0000, interval 0.9075–1.0000, resolved** | 1 bit / 0.999 | 0 / 0.000 |
| 2 | w = 0, φ = π, β = 0 | 1.0 / 1.000 | 1.0 / 1.0000, interval 0.9075–1.0000, resolved | 0 bit / 0.000 | 0 / 0.000 |
| 3 | w = 1, φ = π/2, β = 0 | 0.5 / 0.525 | 0.0 / **0.0303, interval 0.0000–0.1228, includes zero: *No resolved influence at this shot count*** | 1 bit / 0.998 | 1 bit / 0.999 |

Three more seeded samples of Act 3 (seeds 1, 2, 3) read Capacity 0.0020, 0.0088 and
0.0127 with upper limits 0.0945, 0.1013 and 0.1052: always a small positive number, always
an interval that includes zero. If the live Act 3 comes out like that, say exactly what the
page says: the interval includes zero. Never call it a small amount of free will. The
Capacity interval at 1,024 shots per probe can never be narrower than 0.0925 (the Hoeffding
e), which is why Act 1 reads "0.9075 to 1.0000" even when every shot agrees.

## Recording tips

- **Rehearse against a timer** once, then record. Cut silences in editing rather than
  rushing the narration.
- **Make text readable:** record at 1920×1080 with the browser zoomed to 125–150%. Zoom
  into the readings and the Capacity interval; judges watch on laptops.
- **Let the ghost speak:** after each rerun, pause a beat so the previous distribution (the
  muted ghost) and the new one are both visible before the narration moves on.
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
  link that plays **without signing in**. Test the link in a private browser window before
  submitting.

## Accessibility

- **Captions:** provide accurate captions, not unreviewed automatic ones. Upload a caption
  file (SRT/VTT) or burn the captions in. Read through the captions for the Greek letters
  and math ("phi equals pi", "w equals one", "about point nine one to one").
- **Transcript:** paste the final narration below, so the video's content also exists as
  text.
- **Describe the visuals in words:** say the numbers you show ("Capacity one point zero,
  interval point nine one to one"; "Connection one bit"), and never rely on colour alone
  ("the teal branch" must also be "Future 1").
- **No flashing:** avoid rapid cuts or flashing content (no more than three flashes per
  second); the scene's own animation is slow and runs once per completed job.

## Transcript

TODO(team): paste the final narration here after recording.

This effort is supported by Qollab & IonQ
