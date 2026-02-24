import streamlit as st
import numpy as np
import pandas as pd
from datetime import date
import calendar
import elabapi_python
from elabapi_python.rest import ApiException
from warnings import filterwarnings
import datetime
from utils import *

st.title ("eLabFTW Log")

st.header('Select a notebook entry')

entity_type = st.radio(
    'Entry type:',
    options=['experiments', 'items'],
    format_func=lambda x: 'Experiment' if x == 'experiments' else 'Resource',
    horizontal=True,
)
st.session_state['entity_type'] = entity_type

if entity_type == 'experiments':
    names, ids, entries = get_experiments(st.session_state.api_client)
    page_base = 'experiments.php'
else:
    names, ids, entries = get_items(st.session_state.api_client)
    page_base = 'database.php'

if names == []:
    entry_label = 'experiment' if entity_type == 'experiments' else 'resource'
    st.write('No %ss available. Create a new %s first!' % (entry_label, entry_label))
else:
    label = 'Experiment title:' if entity_type == 'experiments' else 'Resource title:'
    exp_name = st.selectbox(label, names, index=0)
    exp_id = ids[names.index(exp_name)]

    st.session_state['exp_name'] = exp_name
    st.session_state['exp_id'] = exp_id

    st.link_button('Open eLabFTW entry', url='https://elabftw-qa-2024.zit.ph.tum.de/%s?mode=view&id=%i' % (page_base, exp_id))
    entry = entries[names.index(exp_name)]
    st.markdown(get_exp_info(st.session_state.api_client, entry))
