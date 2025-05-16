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
    st.session_state["name"] = '' 
    st.session_state["comment"] = '' 


st.title ("eLabFTW Log")

st.header('Create a new experiment')


name = st.text_input('Name:', key='name')
comment = st.text_input('Comment:', key='comment')

st.button('Clear text', on_click=clear_text)
if st.button('Create'):
    create_experiment(st.session_state.api_client, name, comment)
    st.write("Added new experiment %s"%name, )