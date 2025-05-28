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

prompt = st.chat_input("Add comment")
if prompt:
    append_to_experiment(st.session_state.api_client, st.session_state.exp_id, prompt)
    message = "Wrote in experiment %s: %s"%(st.session_state.exp_name,prompt)
    st.session_state["chat_history"].append(message)
    if len(st.session_state["chat_history"]) > 10: 
        st.session_state["chat_history"] = st.session_state["chat_history"][-10:]
    container = st.container(border=True)
    container.write('\n\n'.join(st.session_state["chat_history"]))

#content = st.text_area('Comment:', key='text')

#st.button('Clear text', on_click=clear_text)
#if st.button('Submit'):
#    append_to_experiment(st.session_state.api_client, st.session_state.exp_id, content)
#    st.write("Added comment to %s"%st.session_state.exp_name, )
