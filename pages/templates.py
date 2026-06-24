"""templates.py — Template registry for the ElabFTW Logger.

Two kinds of templates coexist:
  1. Python .py files in the templates/ folder (for complex/conditional logic).
     Each file defines one @st.dialog function whose name contains "template".
     Register new ones in PYTHON_TEMPLATES at the bottom of this file.
  2. YAML .yaml files in the user templates folder (for straightforward field lists).
     Loaded and rendered generically by yaml_template_dialog().
     Add defaults: sections to YAML files to enable the "Fill default values" dropdown.
"""

from pathlib import Path
from warnings import filterwarnings

import streamlit as st
import yaml
from platformdirs import user_config_dir

from template_helpers import _f, reset, _append  # noqa: F401 — re-exported for comment.py compat
from templates.xps_measurement import template_xps_measurement
from templates.xps_reference import template_xps_reference

filterwarnings('ignore')


# ── YAML loader ───────────────────────────────────────────────────────────────

TEMPLATES_DIR = Path(user_config_dir("elab_app")) / "templates"


def load_yaml_templates() -> dict[str, dict]:
    """Return name → parsed YAML dict for every .yaml file in the templates dir."""
    result = {}
    if not TEMPLATES_DIR.exists():
        return result
    for path in sorted(TEMPLATES_DIR.glob("*.yaml")):
        try:
            with open(path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            if isinstance(data, dict) and "name" in data and "fields" in data:
                result[data["name"]] = data
        except Exception as e:
            st.warning(f"Could not load template {path.name}: {e}")
    return result


# ── Generic YAML dialog renderer ─────────────────────────────────────────────

@st.dialog("Fill in the fields")
def yaml_template_dialog(template: dict):
    """Render a form dialog from a parsed YAML template dict."""
    st.write(f"**{template['name']}**")

    fields   = template.get("fields", [])
    defaults = template.get("defaults", [])
    tmpl_key = template['name']

    # ── Defaults selector ────────────────────────────────────────────────────
    if defaults:
        sel_key = f"_yaml_{tmpl_key}_defaults_sel"

        def _apply_defaults():
            chosen_name = st.session_state[sel_key]
            for field in fields:
                label    = field["label"]
                key_base = f"_yaml_{tmpl_key}_{label}"
                if chosen_name == "<empty>":
                    st.session_state.pop(key_base, None)
                    st.session_state.pop(key_base + "_unit", None)
                else:
                    chosen = next((d for d in defaults if d["name"] == chosen_name), None)
                    if not chosen:
                        continue
                    vals = chosen.get("values", {})
                    if label in vals:
                        v     = vals[label]
                        ftype = field.get("type", "text")
                        if ftype == "number":
                            try:
                                st.session_state[key_base] = float(v) if v not in (None, "") else None
                            except (TypeError, ValueError):
                                st.session_state[key_base] = None
                        elif ftype == "sci_number":
                            st.session_state[key_base] = str(v) if v not in (None, "") else ""
                        elif ftype == "select":
                            if v in field.get("options", []):
                                st.session_state[key_base] = v
                        else:  # text, textarea
                            st.session_state[key_base] = str(v) if v is not None else ""
                    unit_label = label + " unit"
                    if unit_label in vals:
                        st.session_state[key_base + "_unit"] = vals[unit_label]

        st.selectbox(
            "Fill default values",
            ["<empty>"] + [d["name"] for d in defaults],
            key=sel_key,
            on_change=_apply_defaults,
        )
        st.divider()

    # ── Fields ───────────────────────────────────────────────────────────────
    values: dict[str, str] = {}

    for field in fields:
        label       = field["label"]
        ftype       = field.get("type", "text")
        units       = field.get("units", [])
        options     = field.get("options", [])
        placeholder = field.get("placeholder", "")
        key_base    = f"_yaml_{tmpl_key}_{label}"

        if ftype == "number":
            if units:
                col_val, col_unit = st.columns([2, 1])
                with col_val:
                    val = st.number_input(label, value=None, key=key_base)
                with col_unit:
                    unit = st.selectbox("Unit", units, key=key_base + "_unit",
                                        label_visibility="hidden")
                values[label] = f"{_f(val, 'g')} {unit}".strip()
            else:
                val = st.number_input(label, value=None, key=key_base)
                values[label] = _f(val, 'g')

        elif ftype == "sci_number":
            if units:
                col_val, col_unit = st.columns([2, 1])
                with col_val:
                    raw = st.text_input(label, placeholder="e.g. 3e-10", key=key_base)
                with col_unit:
                    unit = st.selectbox("Unit", units, key=key_base + "_unit",
                                        label_visibility="hidden")
            else:
                raw  = st.text_input(label, placeholder="e.g. 3e-10", key=key_base)
                unit = ""
            try:
                parsed    = float(raw) if raw.strip() else None
                formatted = _f(parsed, '.3e')
            except ValueError:
                formatted = _f(raw.strip())
            values[label] = f"{formatted} {unit}".strip() if unit else formatted

        elif ftype == "select":
            val = st.selectbox(label, options, key=key_base)
            values[label] = _f(val)

        elif ftype == "textarea":
            val = st.text_area(label, placeholder=placeholder, key=key_base)
            values[label] = _f(val)

        else:  # default: text
            if units:
                col_val, col_unit = st.columns([2, 1])
                with col_val:
                    val = st.text_input(label, placeholder=placeholder, key=key_base)
                with col_unit:
                    unit = st.selectbox("Unit", units, key=key_base + "_unit",
                                        label_visibility="hidden")
                values[label] = f"{_f(val)} {unit}".strip()
            else:
                val = st.text_input(label, placeholder=placeholder, key=key_base)
                values[label] = _f(val)

    if st.button("Submit", on_click=reset):
        output_template = template.get("output", "")
        if not isinstance(output_template, str):
            st.error(
                "⚠️ This template's `output:` field could not be read as text "
                "(YAML parsed it as a non-string type). "
                "Add `|` after `output:` in the YAML file to fix this."
            )
            return
        prompt = output_template
        for label, value in values.items():
            prompt = prompt.replace("{" + label + "}", value)
        st.session_state.prompt = prompt
        _append(prompt)
        st.rerun()


# ── Python template registry ──────────────────────────────────────────────────
# Maps the dropdown label to the @st.dialog function.
# Add new Python templates here after creating their file in templates/.

PYTHON_TEMPLATES = {
    "XPS Measurement":           template_xps_measurement,
    "XPS Reference Measurement": template_xps_reference,
}
