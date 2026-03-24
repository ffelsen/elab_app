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
from version import LOG_SCHEMA_VERSION


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

    # ── elab-app log compatibility check ─────────────────────────────────────
    compat = check_log_compatibility(entry.body)

    # ── surface legacy / other-version tables regardless of main status ──────
    if compat['legacy_tables']:
        st.info(
            f"ℹ️ {compat['legacy_tables']} legacy log table(s) found (no version identifier). "
            "They will not be modified by the app. "
            "You can migrate them manually by copying their rows into a CSV and using the CSV upload."
        )
    if compat['other_versions']:
        st.info(
            f"ℹ️ Log table(s) from a different schema version found: "
            + ", ".join(compat['other_versions'])
            + f" (current: {LOG_SCHEMA_VERSION}). They will not be modified."
        )

    if compat['status'] == 'no_table':
        st.warning(
            "⚠️ This entry does not yet contain an elab-app log table. "
            "The first log you post will create it automatically.\n\n"
            "If you want to create it manually (e.g. to migrate existing content), "
            "paste the following HTML into the elabFTW source editor (**Tools → Source code**) and save:"
        )
        st.code(build_log_table([]), language='html')

    elif compat['status'] == 'ok':
        st.success(
            f"✅ elab-app log table found ({LOG_SCHEMA_VERSION}) — "
            f"{len(compat['rows'])} row(s), all valid."
        )

    elif compat['status'] == 'unordered':
        initials = st.session_state.get('initials', '')
        now_iso  = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        detail = []
        if compat['n_tables'] > 1:
            detail.append(f"{compat['n_tables']} separate log tables (will be merged into one)")
        if not compat['ordered']:
            detail.append("not sorted newest-to-oldest")
        st.warning(
            f"⚠️ elab-app log found ({LOG_SCHEMA_VERSION}) — "
            f"{len(compat['rows'])} row(s), all valid, but: " + "; ".join(detail) + "."
        )
        st.info(
            "You can fix the order by uploading a one-line CSV on the **Add text logs** page "
            "(CSV Upload section). Copy the line below:"
        )
        st.code(f'{now_iso},reordered table according to timestamp,{initials}', language='text')
        if st.button("Fix order now", type="primary", key="fix_order_btn"):
            reorder_row = (now_iso, 'reordered table according to timestamp', initials)
            bulk_append_to_experiment(
                st.session_state.api_client, exp_id, [reorder_row], entity_type=entity_type,
            )
            st.success("✅ Table reordered! Reload the page to confirm.")

    else:  # 'warnings'
        n_ok = len(compat['rows']) - len(compat['bad_rows'])
        st.warning(
            f"⚠️ elab-app log table found ({LOG_SCHEMA_VERSION}) — "
            f"{len(compat['rows'])} row(s), {n_ok} valid, {len(compat['bad_rows'])} with issues:"
        )
        for idx, row, reason in compat['bad_rows']:
            st.markdown(f"- **Row {idx}** (`{row[0]}` / `{row[2]}`): {reason}")
