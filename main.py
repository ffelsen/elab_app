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

st.logo('./content/logo.png', size="large")

filterwarnings('ignore')
with open('digi.key','r') as f:
    key = f.readline().strip()

configuration = elabapi_python.Configuration()
configuration.api_key['api_key'] = key
configuration.api_key_prefix['api_key'] = 'Authorization'
configuration.host = 'https://elabftw-qa-2024.zit.ph.tum.de/api/v2'
configuration.debug = False
configuration.verify_ssl = False
api_client = elabapi_python.ApiClient(configuration)
api_client.set_default_header(header_name='Authorization', header_value=key)

st.session_state['api_client'] = api_client

st.session_state['prompt'] = None

st.set_page_config(
    page_title="ElabFTW Logger",
)

st.write("# Welcome to the ElabFTW log app!")
st.image("content/e-conversion_logo.png")


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


# Define the pages
main_page = st.Page("pages/main_page.py", title="Select experiment")
page_2 = st.Page("pages/create_exp.py", title="Create new experiment")
page_3 = st.Page("pages/comment.py", title="Add comment")
page_4 = st.Page("pages/sketch.py", title="Add sketch")


# Set up navigation
pg = st.navigation([main_page, page_2, page_3, page_4])

# Run the selected page
pg.run()

