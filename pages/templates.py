import streamlit as st
import numpy as np
import pandas as pd
from datetime import date
import calendar
import elabapi_python 
from elabapi_python.rest import ApiException
from warnings import filterwarnings
import datetime
from PIL import Image
from uuid import uuid4
from utils import *


@st.dialog("Fill in the fields")
def template_1():
    st.write(f"Template 1")
    col1, col2 = st.columns(2)
    with col1:
        T = st.number_input("Temperature")
        p = st.number_input("Pressure")
    with col2:
        Tu = st.selectbox('T unit', ['K','°C'])
        pu = st.selectbox('p unit',['bar','torr','PSI'])
    com = st.text_input("Comment")
    if st.button("Submit", on_click = reset):
        prompt = 'Measured at T = %.3f %s and p = %.3f %s\n \n %s'%(T,Tu,p,pu,com)
        st.session_state.prompt = prompt
        entity_type = st.session_state.get('entity_type', 'experiments')
        append_to_experiment(st.session_state.api_client, st.session_state.exp_id, prompt, entity_type=entity_type)
        entry_label = 'experiment' if entity_type == 'experiments' else 'resource'
        message = "Wrote in %s %s: %s" % (entry_label, st.session_state.exp_name, prompt)
        st.session_state["chat_history"].append(message)
        if len(st.session_state["chat_history"]) > 10: 
            st.session_state["chat_history"] = st.session_state["chat_history"][-10:]
        st.rerun()

@st.dialog("Fill in the fields")
def template_2():
    st.write(f"Template 2")
    col1, col2 = st.columns(2)
    with col1:
        T = st.number_input("Temperature")
        p = st.number_input("Pressure")
        e = st.number_input("Excitation wavelenght")
    with col2:
        Tu = st.selectbox('T unit', ['K','°C'])
        pu = st.selectbox('p unit',['bar','torr','PSI'])
        eu = st.selectbox('$\\lambda$ unit',['nm','cm$^{-1}$','eV'])
    com = st.text_input("Comment")
    if st.button("Submit", on_click = reset):
        prompt = 'Measured at T = %.3f %s and p = %.3f %s\n \n Excited at %s %s \n \n %s'%(T,Tu,p,pu,e,eu,com)
        st.session_state.prompt = prompt
        entity_type = st.session_state.get('entity_type', 'experiments')
        append_to_experiment(st.session_state.api_client, st.session_state.exp_id, prompt, entity_type=entity_type)
        entry_label = 'experiment' if entity_type == 'experiments' else 'resource'
        message = "Wrote in %s %s: %s" % (entry_label, st.session_state.exp_name, prompt)
        st.session_state["chat_history"].append(message)
        if len(st.session_state["chat_history"]) > 10: 
            st.session_state["chat_history"] = st.session_state["chat_history"][-10:]
        st.rerun()


@st.dialog("XPS Measurement")
def template_xps_measurement():
    st.write("XPS Measurement Template")
    
    # Check if experiment is selected
    if not st.session_state.get("exp_id"):
        st.error("❌ Please select an experiment first before using this template.")
        if st.button("Close"):
            st.rerun()
        return
    
    # Excitation Energy and Spot Settings
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
    
    # Power and Voltage
    col_pow, col_vol = st.columns(2)
    with col_pow:
        power = st.number_input("Power [W]", min_value=0.0, value=50.0, step=1.0, key="temp_pow")
    with col_vol:
        voltage = st.number_input("Voltage [kV]", min_value=0.0, value=15.0, step=0.1, key="temp_vol")
    
    # Core Levels
    st.markdown("**Core Levels**")
    core_levels = st.text_input("Enter core levels (comma-separated)", 
                                 placeholder="e.g., C 1s, O 1s, Ti 2p", 
                                 key="temp_cores")
    
    # Gas Composition
    st.markdown("**Gas Composition**")
    col_gas1, col_gas2 = st.columns(2)
    with col_gas1:
        gas1 = st.text_input("Gas 1", placeholder="e.g., N2", key="temp_gas1")
        gas2 = st.text_input("Gas 2", placeholder="e.g., O2", key="temp_gas2")
    with col_gas2:
        pressure1 = st.number_input("Pressure 1 [mbar]", min_value=0.0, value=0.0, format="%.2e", key="temp_p1")
        pressure2 = st.number_input("Pressure 2 [mbar]", min_value=0.0, value=0.0, format="%.2e", key="temp_p2")
    
    # Comment
    comment = st.text_area("Comment", placeholder="Additional notes...", key="temp_comment")
    
    if st.button("Submit", on_click=reset):
        # Build the prompt
        prompt_parts = []
        prompt_parts.append(f"**XPS Measurement**")
        prompt_parts.append(f"Excitation: {excite}")
        prompt_parts.append(f"Spot Setting: {spot}")
        prompt_parts.append(f"Power: {power} W, Voltage: {voltage} kV")
        
        if core_levels.strip():
            prompt_parts.append(f"Core Levels: {core_levels}")
        
        # Add gas composition
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
        entity_type = st.session_state.get('entity_type', 'experiments')
        append_to_experiment(st.session_state.api_client, st.session_state.exp_id, prompt, entity_type=entity_type)
        entry_label = 'experiment' if entity_type == 'experiments' else 'resource'
        message = "Wrote XPS measurement in %s %s" % (entry_label, st.session_state.exp_name)
        if "chat_history" not in st.session_state:
            st.session_state["chat_history"] = []
        st.session_state["chat_history"].append(message)
        if len(st.session_state["chat_history"]) > 10:
            st.session_state["chat_history"] = st.session_state["chat_history"][-10:]
        st.rerun()


@st.dialog("XPS Reference Measurement")
def template_xps_reference():
    st.write("XPS Reference Measurement Template")
    
    # Check if experiment is selected
    if not st.session_state.get("exp_id"):
        st.error("❌ Please select an experiment first before using this template.")
        if st.button("Close"):
            st.rerun()
        return
    
    # Excitation Energy and Spot Settings
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
    
    # Power and Voltage
    col_pow, col_vol = st.columns(2)
    with col_pow:
        power = st.number_input("Power [W]", min_value=0.0, value=50.0, step=1.0, key="temp_ref_pow")
    with col_vol:
        voltage = st.number_input("Voltage [kV]", min_value=0.0, value=15.0, step=0.1, key="temp_ref_vol")
    
    # Reference-specific fields
    col_cps, col_ref = st.columns(2)
    with col_cps:
        max_cps = st.number_input("Max. CPS", min_value=0.0, value=100000.0, step=1000.0, key="temp_ref_cps")
    with col_ref:
        ref_peak = st.text_input("Reference Peak", placeholder="e.g., O 1s at 530 eV", key="temp_ref_peak")
    
    # Gas Composition
    st.markdown("**Gas Composition**")
    col_gas1, col_gas2 = st.columns(2)
    with col_gas1:
        gas1 = st.text_input("Gas 1", placeholder="e.g., N2", key="temp_ref_gas1")
        gas2 = st.text_input("Gas 2", placeholder="e.g., O2", key="temp_ref_gas2")
    with col_gas2:
        pressure1 = st.number_input("Pressure 1 [mbar]", min_value=0.0, value=0.0, format="%.2e", key="temp_ref_p1")
        pressure2 = st.number_input("Pressure 2 [mbar]", min_value=0.0, value=0.0, format="%.2e", key="temp_ref_p2")
    
    # Comment
    comment = st.text_area("Comment", placeholder="Additional notes...", key="temp_ref_comment")
    
    if st.button("Submit", on_click=reset):
        # Build the prompt
        prompt_parts = []
        prompt_parts.append(f"**XPS Reference Measurement**")
        prompt_parts.append(f"Excitation: {excite}")
        prompt_parts.append(f"Spot Setting: {spot}")
        prompt_parts.append(f"Power: {power} W, Voltage: {voltage} kV")
        prompt_parts.append(f"Max. CPS: {max_cps:.0f}")
        
        if ref_peak.strip():
            prompt_parts.append(f"Reference Peak: {ref_peak}")
        
        # Add gas composition
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
        entity_type = st.session_state.get('entity_type', 'experiments')
        append_to_experiment(st.session_state.api_client, st.session_state.exp_id, prompt, entity_type=entity_type)
        entry_label = 'experiment' if entity_type == 'experiments' else 'resource'
        message = "Wrote XPS reference measurement in %s %s" % (entry_label, st.session_state.exp_name)
        if "chat_history" not in st.session_state:
            st.session_state["chat_history"] = []
        st.session_state["chat_history"].append(message)
        if len(st.session_state["chat_history"]) > 10:
            st.session_state["chat_history"] = st.session_state["chat_history"][-10:]
        st.rerun()


def reset():
    st.session_state.selection = 'Choose a template'
