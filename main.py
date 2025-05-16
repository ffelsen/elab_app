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

# Define the pages
main_page = st.Page("pages/main_page.py", title="Main Page")
page_2 = st.Page("pages/comment.py", title="Add comment")
page_3 = st.Page("pages/sketch.py", title="Add sketch")

# Set up navigation
pg = st.navigation([main_page, page_2, page_3])

# Run the selected page
pg.run()

