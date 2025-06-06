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
        append_to_experiment(st.session_state.api_client, st.session_state.exp_id, prompt)
        message = "Wrote in experiment %s: %s"%(st.session_state.exp_name,prompt)
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
        append_to_experiment(st.session_state.api_client, st.session_state.exp_id, prompt)
        message = "Wrote in experiment %s: %s"%(st.session_state.exp_name,prompt)
        st.session_state["chat_history"].append(message)
        if len(st.session_state["chat_history"]) > 10: 
            st.session_state["chat_history"] = st.session_state["chat_history"][-10:]
        st.rerun()


def reset():
    st.session_state.selection = 'Choose a template'
