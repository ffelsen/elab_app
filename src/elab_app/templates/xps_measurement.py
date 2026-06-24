import streamlit as st
from template_helpers import _f, reset, _append


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
        power = st.number_input("Power [W]", min_value=0.0, value=None, step=1.0, key="temp_pow")
    with col_vol:
        voltage = st.number_input("Voltage [kV]", min_value=0.0, value=None, step=0.1, key="temp_vol")

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
        pressure1 = st.number_input("Pressure 1 [mbar]", min_value=0.0, value=None, format="%.2e", key="temp_p1")
        pressure2 = st.number_input("Pressure 2 [mbar]", min_value=0.0, value=None, format="%.2e", key="temp_p2")

    comment = st.text_area("Comment", placeholder="Additional notes...", key="temp_comment")

    if st.button("Submit", on_click=reset):
        prompt_parts = [
            "**XPS Measurement**",
            f"Excitation: {excite}",
            f"Spot Setting: {spot}",
            f"Power: {_f(power, '.1f')} W, Voltage: {_f(voltage, '.1f')} kV",
        ]
        if core_levels.strip():
            prompt_parts.append(f"Core Levels: {core_levels}")
        else:
            prompt_parts.append(f"Core Levels: {_f(core_levels)}")
        gases = []
        if gas1.strip() and pressure1 is not None and pressure1 > 0:
            gases.append(f"{gas1} ({pressure1:.2e} mbar)")
        if gas2.strip() and pressure2 is not None and pressure2 > 0:
            gases.append(f"{gas2} ({pressure2:.2e} mbar)")
        if gases:
            prompt_parts.append(f"Gases: {', '.join(gases)}")
        if comment.strip():
            prompt_parts.append(f"Comment: {comment}")
        prompt = "\n".join(prompt_parts)
        st.session_state.prompt = prompt
        _append(prompt)
        st.rerun()
