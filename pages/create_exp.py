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

entity_type = st.radio(
    'Entry type:',
    options=['experiments', 'items'],
    format_func=lambda x: 'Experiment' if x == 'experiments' else 'Resource',
    horizontal=True,
)

if entity_type == 'experiments':
    st.header('Create a new experiment')
    cats, ids, colors = get_categories(st.session_state.api_client, st.session_state.team_id)
else:
    st.header('Create a new resource')
    cats, ids = get_resource_categories(st.session_state.api_client)

cat = st.selectbox('Category', cats, index=0)

if cat is None:
    entry_label = 'experiment' if entity_type == 'experiments' else 'resource'
    st.write('Please select a %s category' % entry_label)
else:
    cat_ind = cats.index(cat)

name = st.text_input('Name:', key='name')
comment = st.text_input('Comment:', key='comment')

st.button('Clear text', on_click=clear_text)
if st.button('Create'):
    if entity_type == 'experiments':
        create_experiment(st.session_state.api_client, name, comment, ids[cat_ind])
        st.write("Added new experiment %s" % name)
    else:
        create_item(st.session_state.api_client, name, comment, ids[cat_ind])
        st.write("Added new resource %s" % name)
