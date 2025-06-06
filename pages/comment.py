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

def clear_text(): 
  st.session_state["text"] = '' 


st.title ("eLabFTW Log")

st.header('Add a comment to the notebook')

if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

exp_chat = st.expander("Chat mode")

with exp_chat:     
    prompt = st.chat_input("Add comment")
    if prompt:
        append_to_experiment(st.session_state.api_client, st.session_state.exp_id, prompt)
        message = "Wrote in experiment %s: %s"%(st.session_state.exp_name,prompt)
        st.session_state["chat_history"].append(message)
        if len(st.session_state["chat_history"]) > 10: 
            st.session_state["chat_history"] = st.session_state["chat_history"][-10:]
        container = st.container(border=True)
        container.write('\n\n'.join(st.session_state["chat_history"]))



exp_temp = st.expander("Template mode")
templates = ['Choose a template',] + [i for i in locals().keys() if 'template' in i]
with exp_temp:     
    temp = st.selectbox('Choose a template', templates, key='selection')
    if temp != 'Choose a template':
        locals()[temp]()
    container = st.container(border=True)
    container.write('\n\n'.join(st.session_state["chat_history"]))
