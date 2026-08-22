"""Custom CSS for the config window. Loaded once by the application."""

from __future__ import annotations

# Quick-pick swatches shown in color panels (curated, vivid on dark bg).
SWATCHES = (
    "#00FFFF",
    "#3584E4",
    "#9141AC",
    "#FF00AA",
    "#FF3300",
    "#FF7800",
    "#F6D32D",
    "#2EC27E",
    "#FFFFFF",
)

CSS = """
.avell-bg {
  background: linear-gradient(160deg, #10131c 0%, #0a0c12 45%, #070810 100%);
}

.avell-title {
  font-weight: 800;
  font-size: 17px;
  letter-spacing: 0.12em;
}

.avell-subtitle {
  font-size: 11px;
  letter-spacing: 0.22em;
  color: rgba(255, 255, 255, 0.38);
}

.glass-card {
  background: rgba(255, 255, 255, 0.045);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 16px;
  padding: 14px;
}

.device-card {
  background: rgba(255, 255, 255, 0.045);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 16px;
  padding: 14px;
}

.section-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.18em;
  color: rgba(255, 255, 255, 0.42);
}

.card-title {
  font-weight: 700;
  font-size: 13px;
}

.dim-label {
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
}

.mode-pills {
  background: rgba(255, 255, 255, 0.06);
  border-radius: 999px;
  padding: 4px;
}

.mode-pill {
  border-radius: 999px;
  padding: 6px 18px;
  background: transparent;
  border: none;
  box-shadow: none;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.55);
  min-height: 30px;
}

.mode-pill:hover {
  background: rgba(255, 255, 255, 0.07);
  color: rgba(255, 255, 255, 0.85);
}

.mode-pill:checked {
  background: linear-gradient(135deg, rgba(0, 255, 255, 0.22), rgba(145, 65, 172, 0.30));
  color: #ffffff;
  box-shadow: 0 0 12px rgba(0, 255, 255, 0.12);
}

.swatch {
  border-radius: 999px;
  min-width: 12px;
  min-height: 12px;
  padding: 0;
  border: 2px solid rgba(255, 255, 255, 0.12);
  background-clip: padding-box;
  box-shadow: none;
}

.swatch-flow flowboxchild {
  padding: 0;
}

.swatch:hover {
  border-color: rgba(255, 255, 255, 0.55);
}

.preset-chip {
  border-radius: 999px;
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: none;
}

.preset-chip:hover {
  background: rgba(255, 255, 255, 0.11);
  border-color: rgba(255, 255, 255, 0.2);
}

.preset-delete {
  min-width: 18px;
  min-height: 18px;
  padding: 0;
  border-radius: 999px;
  background: transparent;
  color: rgba(255, 255, 255, 0.35);
  box-shadow: none;
  border: none;
}

.preset-delete:hover {
  color: #ff6b6b;
  background: rgba(255, 107, 107, 0.12);
}

.status-dot {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.45);
}

.pill-button {
  border-radius: 999px;
  padding: 6px 16px;
  font-weight: 600;
}

.accent-apply {
  background: linear-gradient(135deg, #00d5ff, #9141ac);
  color: #ffffff;
  border-radius: 999px;
  padding: 8px 20px;
  font-weight: 700;
  border: none;
  box-shadow: 0 2px 10px rgba(0, 213, 255, 0.18);
}

.accent-apply:hover {
  background: linear-gradient(135deg, #2fdeff, #a555c0);
}

.solar-day-card {
  background: linear-gradient(160deg, rgba(246, 211, 45, 0.10), rgba(255, 255, 255, 0.03));
  border: 1px solid rgba(246, 211, 45, 0.18);
  border-radius: 16px;
  padding: 14px;
}

.solar-night-card {
  background: linear-gradient(160deg, rgba(53, 132, 228, 0.12), rgba(255, 255, 255, 0.02));
  border: 1px solid rgba(53, 132, 228, 0.22);
  border-radius: 16px;
  padding: 14px;
}

.off-hint {
  color: rgba(255, 255, 255, 0.35);
  font-size: 13px;
}

.entry-slim {
  border-radius: 10px;
}
"""
