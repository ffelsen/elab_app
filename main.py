import streamlit as st
import numpy as np
from datetime import date
import elabapi_python
from elabapi_python.rest import ApiException
from utils import *
from urllib.parse import urlparse
from warnings import filterwarnings
filterwarnings('ignore')

#### initialize session state ####
def init_session_state():
    defaults = {
        "api_client": None,
        "prompt": None,
        "team_id": None,
        "team": None,
        "exp_id": None,
        "exp_directory": None,
        "positions": [],
        "angles": [],
        "api_key": "",
        "host_domain": "",
        "sample_id": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
init_session_state()

#### configure eLab api ####
with open('digi.key','r') as f:
    key = f.readline().strip()
configuration = elabapi_python.Configuration()
configuration.api_key['api_key'] = key
configuration.api_key_prefix['api_key'] = 'Authorization'
configuration.host = 'https://elabftw-qa-2024.zit.ph.tum.de/api/v2'
configuration.debug = False
configuration.verify_ssl = False
st.session_state['api_client'] = elabapi_python.ApiClient(configuration)
st.session_state['api_client'].set_default_header(header_name='Authorization', header_value=key)

st.session_state['api_key'] = key
st.session_state['host_domain'] = urlparse(configuration.host)
st.session_state['host_domain'] = f"{st.session_state['host_domain'].scheme}://{st.session_state['host_domain'].netloc}"

#### setup some streamlit stuff####
st.logo('./content/logo.png', size="large")
st.set_page_config(
    page_title="ElabFTW Logger",
)

#### Handel Login ####
@st.dialog("Login")
def login():
    st.write("Please type your name here:")
    fn = st.text_input('first name', 'Test')
    ln = st.text_input('last name', 'Account')
    if fn:
        try:
            tids, teams = get_teams(st.session_state.api_client, get_user_id(st.session_state.api_client, fn, ln))
            team = st.selectbox('Team', teams, index=0)
        except:
            st.write('Please select valid user')
    if st.button("login"):
        st.session_state['fn'] = fn
        st.session_state['ln'] = ln
        st.session_state['team_id'] = tids[teams.index(team)]
        st.session_state['team'] = team
        st.rerun()

if "fn" not in st.session_state or "ln" not in st.session_state:
    login()
else:
    f"You are logged in as {st.session_state['fn']} {st.session_state['ln']} in Team {st.session_state['team']}"

#### Define the pages ####
exp_page = st.Page("pages/exp_page.py", title="Experiment Overview")
sample_page = st.Page("pages/sample_page.py", title="Define Samples")
pos_page = st.Page("pages/position_page.py", title="Define Positions")
treat_page = st.Page("pages/treatment_page.py", title="Treatment Steps")
mess_page = st.Page("pages/measurement_page.py", title="Measurements")
comment_page = st.Page("pages/comment.py", title="Comment")
sketch_page = st.Page("pages/sketch.py", title="Sketch")

pg = st.navigation([exp_page, sample_page, pos_page, treat_page, mess_page, comment_page, sketch_page])

# Run the selected page
pg.run()

