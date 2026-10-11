// Persona tabs: the WAI-ARIA tabs pattern with automatic activation. The tablist
// holds buttons with role="tab"; Left/Right/Home/End move between them with a
// roving tabindex, and the matching role="tabpanel" is shown. Switching a persona
// changes explanation text only: main.js never replaces data on a tab change.
// No imports: main.js passes the dom helpers in.

export function createTabs(lib, items, onChange) {
  let current = 0;
  for (let i = 0; i < items.length; i++) {
    if (items[i].tab.getAttribute("aria-selected") === "true") current = i;
  }

  function show(i, focus) {
    current = i;
    items.forEach((it, j) => {
      const on = j === i;
      it.tab.setAttribute("aria-selected", on ? "true" : "false");
      it.tab.setAttribute("tabindex", on ? "0" : "-1");
      it.panel.hidden = !on;
    });
    if (focus) items[i].tab.focus();
    if (onChange) onChange(items[i].key);
  }

  items.forEach((it, i) => {
    it.tab.addEventListener("click", () => {
      if (i !== current) show(i, false);
    });
    it.tab.addEventListener("keydown", (ev) => {
      const n = items.length;
      let next = null;
      if (ev.key === "ArrowRight") next = (i + 1) % n;
      else if (ev.key === "ArrowLeft") next = (i - 1 + n) % n;
      else if (ev.key === "Home") next = 0;
      else if (ev.key === "End") next = n - 1;
      if (next === null) return;
      ev.preventDefault();
      show(next, true);
    });
  });

  // Apply the initial state without announcing a change.
  const saved = onChange;
  onChange = null;
  show(current, false);
  onChange = saved;

  return {
    current: () => items[current].key,
    select(key, focus) {
      const i = items.findIndex((it) => it.key === key);
      if (i >= 0) show(i, !!focus);
    },
  };
}
