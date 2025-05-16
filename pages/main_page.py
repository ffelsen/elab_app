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
names, ids, exps = get_experiments(st.session_state.api_client)


exp_name = st.selectbox('Experiment title:', names, index=0)
exp_id = ids[names.index(exp_name)]

st.session_state['exp_name'] = exp_name
st.session_state['exp_id'] = exp_id

st.link_button('Open eLabFTW entry', url ='https://elabftw-qa-2024.zit.ph.tum.de/experiments.php?mode=view&id=%i'%exp_id)
