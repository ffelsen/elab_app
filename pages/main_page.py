import streamlit as st
import numpy as np
import pandas as pd
from datetime import date
import calendar
import elabapi_python
from elabapi_python.rest import ApiException
from warnings import filterwarnings
import datetime
import json
import os
from utils import *


@st.dialog('Download elabFTW entry')
def download_dialog(exp_id: int, exp_name: str, entity_type: str):
    """Fetch the entry as JSON and save it to a user-chosen path."""
    safe_name = exp_name.replace('/', '_').replace(' ', '_')
    default_path = os.path.join(os.path.expanduser('~'), 'Downloads', f'{safe_name}.json')

    save_path = st.text_input('Save to', value=default_path)

    if st.button('Save', type='primary', use_container_width=True):
        try:
            if entity_type == 'items':
                api = elabapi_python.ItemsApi(st.session_state.api_client)
                data = api.get_item(exp_id)
            else:
                api = elabapi_python.ExperimentsApi(st.session_state.api_client)
                data = api.get_experiment(exp_id)

            payload = st.session_state.api_client.sanitize_for_serialization(data)
            os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
            st.success(f'Saved to `{save_path}`')
        except Exception as e:
            st.error(f'Could not save file: {e}')


st.title ("eLabFTW Log")

st.header('Select a notebook entry')

_options = ['experiments', 'items']
_saved_type = st.session_state.get('entity_type', 'experiments')
_default_type = _options.index(_saved_type) if _saved_type in _options else 0
entity_type = st.radio(
    'Entry type:',
    options=_options,
    format_func=lambda x: 'Experiment' if x == 'experiments' else 'Resource',
    horizontal=True,
    index=_default_type,
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
    saved_name = st.session_state.get('exp_name', '')
    default_index = names.index(saved_name) if saved_name in names else 0
    exp_name = st.selectbox(label, names, index=default_index)
    exp_id = ids[names.index(exp_name)]

    st.session_state['exp_name'] = exp_name
    st.session_state['exp_id'] = exp_id

    col_open, col_dl = st.columns(2)
    col_open.link_button('Open eLabFTW entry',
                        #  url='https://elabftw-qa-2024.zit.ph.tum.de/%s?mode=view&id=%i' % (page_base, exp_id),
                         url='https://elntest.ub.tum.de/%s?mode=view&id=%i' % (page_base, exp_id),
                         use_container_width=True)
    if col_dl.button('Download elabFTW entry', use_container_width=True):
        download_dialog(exp_id, exp_name, entity_type)

    entry = entries[names.index(exp_name)]
    st.markdown(get_exp_info(st.session_state.api_client, entry))
