"""The flat drawn scenes (qollab_project/ui/plate.js) that the four design themes select.

Static contract checks, like tests/test_ui_static.py; the drawing itself is checked in a
browser (dev/index.html?theme=a..d).
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


PLATE = "qollab_project/ui/plate.js"


def test_plate_keeps_the_scene_mappings():
    code = _read(PLATE)
    assert "const RMAX = 52;" in code and "RMAX * Math.cbrt(" in code       # radius ~ cbrt(p)
    assert "2 + 10 * p[i]" in code                                          # branch 2 + 10 p ...
    assert '"vector-effect": "non-scaling-stroke"' in code                  # ... in screen pixels
    assert "const bw = 4 + 6 * I;" in code and "0.15 + 0.85 * I" in code    # bridge follows connection, at most 10 px
    assert "placeholder ? 4 : 4 + 6 * I" in _read("qollab_project/ui/scene.js")    # both views agree
    assert "const N_PART = 40;" in code and "Math.round(to.p1 * N_PART)" in code


def test_future_one_is_upper_right_as_the_scene_text_says():
    code = _read(PLATE)
    assert "const FC = [[512, 300], [512, 112]];" in code     # index 0 lower right, 1 upper right
    text = _read("qollab_project/ui/text.js")
    assert "upper right sphere" in text and "lower right sphere" in text


def test_plate_has_the_same_api_and_text_alternative_as_the_3d_view():
    plate = _read(PLATE)
    scene = _read("qollab_project/ui/scene.js")
    for name in ("setResult", "setLabel", "setMotion", "setReducedMotion", "motion", "resize", "dispose", "canvas"):
        assert "api." + name + " =" in plate, name
        assert "api." + name + " =" in scene, name
    assert 'role: "img"' in plate and '"aria-label"' in plate


def test_plate_motion_is_decoration_only():
    code = _read(PLATE)
    assert "requestAnimationFrame" in code and "root.isConnected" in code
    assert "if (reduced) {" in code and "anim = null;" in code          # reduced motion: no transition
    assert "fn(target, narrow)" in code                                  # annotations show the run's numbers
    assert "Math.random" not in code


def test_the_four_styles_exist_and_each_theme_selects_its_own():
    code = _read(PLATE)
    for t in "abcd":
        assert re.search(r"(?m)^  %s\(c\) \{$" % t, code), t
        css = _read("dev/themes/theme-%s.css" % t)
        assert "--fwo-scene-plate: %s;" % t in css, t
        assert '#fwo-app[data-theme="%s"] .fwo-plate text' % t in css, t


def test_main_picks_the_plate_from_the_theme_variable():
    main = _read("qollab_project/main.js")
    assert 'import { createPlate } from "./ui/plate.js";' in main
    assert 'getPropertyValue("--fwo-scene-plate")' in main and "/^[abcd]$/.test(v)" in main
    assert "const scene = plateStyle\n    ? createPlate(dom, el.sceneHost, " in main
    assert ": createScene(THREE, dom, el.sceneHost, " in main            # no theme: the 3D view


def test_main_css_sizes_the_plate_and_stops_its_twinkle():
    css = _read("qollab_project/main.css")
    assert "#fwo-app .fwo-scene .fwo-scene-host.fwo-scene-host--plate { height: auto; aspect-ratio: 660 / 420; }" in css
    assert "#fwo-app .fwo-plate--still .fwo-plate-twinkle { animation: none; }" in css
    assert "@keyframes fwo-plate-twinkle" in css


def test_bridge_enters_the_self_and_shimmers_only_with_motion_and_connection():
    code = _read(PLATE)
    assert 'const BRIDGE = "M 156,300 C 172,272 185,250 185,226 L 185,206";' in code   # World up into the Self
    assert "const on = motion && !state.placeholder && I > 0.02;" in code
    assert "opacity: (0.9 * I).toFixed(3)" in code and "const n = 1 + Math.round(3 * I);" in code
    assert "shimmerAt = (shimmerAt - ((shimmerLen || 196) / SHIMMER_S) * dt) % 100000;" in code
    # the bridge is drawn before the brain, so it rises behind the translucent lobe shells
    for t in "abcd":
        body = code[code.index("  %s(c) {" % t):]
        assert body.index("c.bridge(") < body.index("c.brain("), t


def test_the_self_body_is_layered_over_the_bridge():
    code = _read(PLATE)
    body = code[code.index("    brain(o) {"):]
    assert body.index('const body = c.add("g", { opacity: o.body[1] });') < body.index('for (const L of LOBES) c.add("ellipse", lobe(L, o.shell));')
    for t in "abcd":
        style = code[code.index("  %s(c) {" % t):]
        assert style.index("c.bridge(") < style.index("c.brain({ body: ["), t


def test_the_constellation_is_a_glowing_point_cloud_that_drifts_only_with_motion():
    code = _read(PLATE)
    assert "const DRIFT = 0.07;" in code and "const DRIFT_MS = 2600;" in code       # the 3D view's sway
    step = code[code.index("  function step(now) {"):]
    assert step.index("if (motion) {") < step.index("drawBrain(BRAIN_TILT[1] + DRIFT * Math.sin(now / DRIFT_MS))")
    assert "if (!motion) drawBrain(BRAIN_TILT[1]);" in code                         # still: the resting layout
    for t in "abcd":
        style = code[code.index("  %s(c) {" % t):]
        assert "node: { core: {" in style[:style.index("c.selfLabel(")], t
        assert "glow: [[0," in style[:style.index("c.selfLabel(")], t


def test_ports_from_the_design_review():
    code = _read(PLATE)
    assert '"\\u00d8 = 104 \\u00b7 \\u221bp"' in code                          # diameter, not radius
    a = code[code.index("  a(c) {"):code.index("  b(c) {")]
    assert a.count("c.tag(") == 2 and "bridgeTagText(v.I, narrow)" in a           # printed labels on A
    for t in "abd":
        css = _read("dev/themes/theme-%s.css" % t)
        line = [ln for ln in css.splitlines() if ln.startswith('#fwo-app[data-theme="%s"] .fwo-dialogue-text {' % t)][0]
        assert "italic" in line, t
