import streamlit as st
import numpy as np
import pandas as pd
from datetime import date
import calendar
import elabapi_python 
from elabapi_python.rest import ApiException
from warnings import filterwarnings
import datetime
filterwarnings('ignore')
from utils import *
import pages.templates as templates
from pages.create_transcript import transcription_widget

def clear_text(): 
  st.session_state["text"] = '' 


st.title ("eLabFTW Log")

st.header('Add a comment to the notebook')

def chat_history_callback(transcript_text, include_timestamps):
    """Callback function to add transcript to chat history and eLabFTW"""
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    entity_type = st.session_state.get('entity_type', 'experiments')
    entry_label = 'experiment' if entity_type == 'experiments' else 'resource'

    # Format message for chat history
    if include_timestamps:
        message = f"Added timestamped transcription to {entry_label} {st.session_state.exp_name}: {transcript_text[:100]}..."
    else:
        message = f"Added transcription to {entry_label} {st.session_state.exp_name}: {transcript_text[:100]}..."
    
    st.session_state["chat_history"].append(message)
    if len(st.session_state["chat_history"]) > 10: 
        st.session_state["chat_history"] = st.session_state["chat_history"][-10:]


if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

exp_chat = st.expander("Chat mode")

with exp_chat:
    prompt = st.chat_input("Add comment")
    if prompt:
        entity_type = st.session_state.get('entity_type', 'experiments')
        append_to_experiment(st.session_state.api_client, st.session_state.exp_id, prompt, entity_type=entity_type)
        entry_label = 'experiment' if entity_type == 'experiments' else 'resource'
        message = "Wrote in %s %s: %s" % (entry_label, st.session_state.exp_name, prompt)
        st.session_state["chat_history"].append(message)
        if len(st.session_state["chat_history"]) > 10: 
            st.session_state["chat_history"] = st.session_state["chat_history"][-10:]
        container = st.container(border=True)
        container.write('\n\n'.join(st.session_state["chat_history"]))



exp_temp = st.expander("Template mode")

# ── Build unified template list ───────────────────────────────────────────────
# Python templates: from the explicit registry in templates.py
_py_templates = templates.PYTHON_TEMPLATES  # display name → function

# YAML templates: loaded from the templates/ folder
_yaml_templates = templates.load_yaml_templates()  # display name → dict

_all_options = ['Choose a template'] + list(_py_templates.keys()) + list(_yaml_templates.keys())

with exp_temp:
    temp = st.selectbox('Choose a template', _all_options, key='selection')
    if temp != 'Choose a template':
        if temp in _yaml_templates:
            # Render via the generic YAML dialog
            templates.yaml_template_dialog(_yaml_templates[temp])
        else:
            # Call the registered Python dialog function
            _py_templates[temp]()
    if len(st.session_state['chat_history']) != 0:
        container = st.container(border=True)
        container.write('\n\n'.join(st.session_state["chat_history"]))


exp_transcriber = st.expander("Voice Transcription")

with exp_transcriber:
    
    # Use the transcription widget with callback
    transcription_widget(
        key_suffix="_comment", 
        on_upload_callback=chat_history_callback, 
        compact_mode=True
    )


