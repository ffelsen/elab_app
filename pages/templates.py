"""templates.py — Template registry for the ElabFTW Logger.

Two kinds of templates coexist:
  1. Python functions decorated with @st.dialog (for complex/conditional logic).
     Naming convention: the function name must contain the word "template".
  2. YAML files in the templates/ folder (for straightforward field lists).
     These are loaded and rendered generically by yaml_template_dialog().

comment.py discovers both kinds and merges them into one dropdown.
"""

import re
from pathlib import Path

import streamlit as st
import yaml
from warnings import filterwarnings
import datetime
from utils import *

filterwarnings('ignore')

# ── Helpers ───────────────────────────────────────────────────────────────────

def reset():
    st.session_state.selection = 'Choose a template'



def _append(prompt: str):
    """Write *prompt* to the current elabFTW entry and update chat history."""
    entity_type = st.session_state.get('entity_type', 'experiments')
    append_to_experiment(
        st.session_state.api_client,
        st.session_state.exp_id,
        prompt,
        entity_type=entity_type,
    )
    entry_label = 'experiment' if entity_type == 'experiments' else 'resource'
    message = "Wrote in %s %s: %s" % (entry_label, st.session_state.exp_name, prompt[:80])
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []
    st.session_state["chat_history"].append(message)
    if len(st.session_state["chat_history"]) > 10:
        st.session_state["chat_history"] = st.session_state["chat_history"][-10:]


# ── YAML loader ───────────────────────────────────────────────────────────────

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def load_yaml_templates() -> dict[str, dict]:
    """Return a dict mapping template name → parsed YAML dict for every
    .yaml file found in the templates/ directory."""
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

    fields = template.get("fields", [])
    values: dict[str, str] = {}   # label → formatted string for output

    for field in fields:
        label = field["label"]
        ftype = field.get("type", "text")
        units = field.get("units", [])
        options = field.get("options", [])
        placeholder = field.get("placeholder", "")
        key_base = f"_yaml_{template['name']}_{label}"

        if ftype == "number":
            col_val, col_unit = (st.columns([2, 1]) if units else (st, None))
            with col_val:
                val = st.number_input(label, key=key_base)
            if units and col_unit:
                with col_unit:
                    unit = st.selectbox("Unit", units, key=key_base + "_unit",
                                        label_visibility="hidden")
                values[label] = f"{val:.3f} {unit}"
            else:
                values[label] = f"{val:.3f}"

        elif ftype == "sci_number":
            col_val, col_unit = (st.columns([2, 1]) if units else (st, None))
            with col_val:
                raw = st.text_input(label, placeholder="e.g. 3e-10",
                                    key=key_base)
            if units and col_unit:
                with col_unit:
                    unit = st.selectbox("Unit", units, key=key_base + "_unit",
                                        label_visibility="hidden")
            else:
                unit = ""
            # Parse and reformat, fall back to raw string if unparseable
            try:
                parsed = float(raw) if raw.strip() else 0.0
                formatted = f"{parsed:.3e}"
            except ValueError:
                formatted = raw.strip()
            values[label] = f"{formatted} {unit}".strip() if unit else formatted

        elif ftype == "select":
            val = st.selectbox(label, options, key=key_base)
            values[label] = val or ""

        elif ftype == "textarea":
            val = st.text_area(label, placeholder=placeholder, key=key_base)
            values[label] = val or ""

        else:  # default: text
            val = st.text_input(label, placeholder=placeholder, key=key_base)
            values[label] = val or ""

    if st.button("Submit", on_click=reset):
        # Substitute {Label} placeholders in the output string
        output_template = template.get("output", "")
        prompt = output_template
        for label, value in values.items():
            prompt = prompt.replace("{" + label + "}", value)
        st.session_state.prompt = prompt
        _append(prompt)
        st.rerun()


# ── Python templates (complex / conditional logic) ────────────────────────────

@st.dialog("XPS Measurement")
def template_xps_measurement():
    st.write("XPS Measurement Template")

    if not st.session_state.get("exp_id"):
        st.error("❌ Please select an experiment first before using this template.")
        if st.button("Close"):
            st.rerun()
        return

    excitation_energies = ["Al K α₁ (1486.6 eV)", "Ag L α₁ (2984.3 eV)", "Cr K α₁ (5414.8 eV)"]
    spot_settings = [
        ["Al 120um 50W", "Al 250um 100W", "Al 330um 150W", "Al 70um 20W"],
        ["Ag 130um 25W", "Ag 260um 50W", "Ag 370um 75W", "Ag 500um 100W", "Ag 70um 10W"],
        ["Cr 200um 10W", "Cr 200um 10W (Energy = 23kV)", "Cr 200um 25W", "Cr 330um 50W",
         "Cr 330um 50W (Energy = 23kV)", "Cr 430um 75W", "Cr 530um 100W"]
    ]

    col_exc, col_spot = st.columns(2)
    with col_exc:
        excite = st.selectbox("Excitation Energy:", excitation_energies, key="temp_exc")
    with col_spot:
        idx = excitation_energies.index(excite) if excite in excitation_energies else 0
        spot = st.selectbox("Spot:", spot_settings[idx], key="temp_spot")

    col_pow, col_vol = st.columns(2)
    with col_pow:
        power = st.number_input("Power [W]", min_value=0.0, value=50.0, step=1.0, key="temp_pow")
    with col_vol:
        voltage = st.number_input("Voltage [kV]", min_value=0.0, value=15.0, step=0.1, key="temp_vol")

    st.markdown("**Core Levels**")
    core_levels = st.text_input("Enter core levels (comma-separated)",
                                placeholder="e.g., C 1s, O 1s, Ti 2p",
                                key="temp_cores")

    st.markdown("**Gas Composition**")
    col_gas1, col_gas2 = st.columns(2)
    with col_gas1:
        gas1 = st.text_input("Gas 1", placeholder="e.g., N2", key="temp_gas1")
        gas2 = st.text_input("Gas 2", placeholder="e.g., O2", key="temp_gas2")
    with col_gas2:
        pressure1 = st.number_input("Pressure 1 [mbar]", min_value=0.0, value=0.0, format="%.2e", key="temp_p1")
        pressure2 = st.number_input("Pressure 2 [mbar]", min_value=0.0, value=0.0, format="%.2e", key="temp_p2")

    comment = st.text_area("Comment", placeholder="Additional notes...", key="temp_comment")

    if st.button("Submit", on_click=reset):
        prompt_parts = [
            "**XPS Measurement**",
            f"Excitation: {excite}",
            f"Spot Setting: {spot}",
            f"Power: {power} W, Voltage: {voltage} kV",
        ]
        if core_levels.strip():
            prompt_parts.append(f"Core Levels: {core_levels}")
        gases = []
        if gas1.strip() and pressure1 > 0:
            gases.append(f"{gas1} ({pressure1:.2e} mbar)")
        if gas2.strip() and pressure2 > 0:
            gases.append(f"{gas2} ({pressure2:.2e} mbar)")
        if gases:
            prompt_parts.append(f"Gases: {', '.join(gases)}")
        if comment.strip():
            prompt_parts.append(f"Comment: {comment}")
        prompt = "\n".join(prompt_parts)
        st.session_state.prompt = prompt
        _append(prompt)
        st.rerun()


@st.dialog("XPS Reference Measurement")
def template_xps_reference():
    st.write("XPS Reference Measurement Template")

    if not st.session_state.get("exp_id"):
        st.error("❌ Please select an experiment first before using this template.")
        if st.button("Close"):
            st.rerun()
        return

    excitation_energies = ["Al K α₁ (1486.6 eV)", "Ag L α₁ (2984.3 eV)", "Cr K α₁ (5414.8 eV)"]
    spot_settings = [
        ["Al 120um 50W", "Al 250um 100W", "Al 330um 150W", "Al 70um 20W"],
        ["Ag 130um 25W", "Ag 260um 50W", "Ag 370um 75W", "Ag 500um 100W", "Ag 70um 10W"],
        ["Cr 200um 10W", "Cr 200um 10W (Energy = 23kV)", "Cr 200um 25W", "Cr 330um 50W",
         "Cr 330um 50W (Energy = 23kV)", "Cr 430um 75W", "Cr 530um 100W"]
    ]

    col_exc, col_spot = st.columns(2)
    with col_exc:
        excite = st.selectbox("Excitation Energy:", excitation_energies, key="temp_ref_exc")
    with col_spot:
        idx = excitation_energies.index(excite) if excite in excitation_energies else 0
        spot = st.selectbox("Spot:", spot_settings[idx], key="temp_ref_spot")

    col_pow, col_vol = st.columns(2)
    with col_pow:
        power = st.number_input("Power [W]", min_value=0.0, value=50.0, step=1.0, key="temp_ref_pow")
    with col_vol:
        voltage = st.number_input("Voltage [kV]", min_value=0.0, value=15.0, step=0.1, key="temp_ref_vol")

    col_cps, col_ref = st.columns(2)
    with col_cps:
        max_cps = st.number_input("Max. CPS", min_value=0.0, value=100000.0, step=1000.0, key="temp_ref_cps")
    with col_ref:
        ref_peak = st.text_input("Reference Peak", placeholder="e.g., O 1s at 530 eV", key="temp_ref_peak")

    st.markdown("**Gas Composition**")
    col_gas1, col_gas2 = st.columns(2)
    with col_gas1:
        gas1 = st.text_input("Gas 1", placeholder="e.g., N2", key="temp_ref_gas1")
        gas2 = st.text_input("Gas 2", placeholder="e.g., O2", key="temp_ref_gas2")
    with col_gas2:
        pressure1 = st.number_input("Pressure 1 [mbar]", min_value=0.0, value=0.0, format="%.2e", key="temp_ref_p1")
        pressure2 = st.number_input("Pressure 2 [mbar]", min_value=0.0, value=0.0, format="%.2e", key="temp_ref_p2")

    comment = st.text_area("Comment", placeholder="Additional notes...", key="temp_ref_comment")

    if st.button("Submit", on_click=reset, key="submit_xps_ref"):
        prompt_parts = [
            "**XPS Reference Measurement**",
            f"Excitation: {excite}",
            f"Spot Setting: {spot}",
            f"Power: {power} W, Voltage: {voltage} kV",
            f"Max. CPS: {max_cps:.0f}",
        ]
        if ref_peak.strip():
            prompt_parts.append(f"Reference Peak: {ref_peak}")
        gases = []
        if gas1.strip() and pressure1 > 0:
            gases.append(f"{gas1} ({pressure1:.2e} mbar)")
        if gas2.strip() and pressure2 > 0:
            gases.append(f"{gas2} ({pressure2:.2e} mbar)")
        if gases:
            prompt_parts.append(f"Gases: {', '.join(gases)}")
        if comment.strip():
            prompt_parts.append(f"Comment: {comment}")
        prompt = "\n".join(prompt_parts)
        st.session_state.prompt = prompt
        _append(prompt)
        st.rerun()


# ── Populate registry ─────────────────────────────────────────────────────────
# Maps the display name shown in the dropdown to the dialog function.
# Add new Python templates here — must stay at the bottom of this file,
# after all function definitions, to avoid NameErrors.
PYTHON_TEMPLATES = {
    "XPS Measurement":           template_xps_measurement,
    "XPS Reference Measurement": template_xps_reference,
}
