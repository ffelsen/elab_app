import streamlit as st
import pandas as pd
import datetime
from warnings import filterwarnings
filterwarnings('ignore')
from utils import *
import markdown as md
import pages.templates as templates
from pages.create_transcript import transcription_widget
from auth import is_valid_short_name

st.title("eLabFTW Log")
st.header('Add a comment to the notebook')


# ── Chat mode ─────────────────────────────────────────────────────────────────
exp_chat = st.expander("Chat mode")

with exp_chat:
    prompt = st.chat_input("Add comment")
    if prompt:
        entity_type = st.session_state.get('entity_type', 'experiments')
        append_to_experiment(
            st.session_state.api_client, st.session_state.exp_id, prompt,
            entity_type=entity_type, initials=st.session_state.get('initials', ''),
        )


# ── Template mode ─────────────────────────────────────────────────────────────
exp_temp = st.expander("Template mode")

_py_templates   = templates.PYTHON_TEMPLATES
_yaml_templates = templates.load_yaml_templates()
_all_options    = ['Choose a template'] + list(_py_templates.keys()) + list(_yaml_templates.keys())

with exp_temp:
    temp = st.selectbox('Choose a template', _all_options, key='selection')
    if temp != 'Choose a template':
        if temp in _yaml_templates:
            templates.yaml_template_dialog(_yaml_templates[temp])
        else:
            _py_templates[temp]()


# ── Voice Transcription ───────────────────────────────────────────────────────
exp_transcriber = st.expander("Voice Transcription")

with exp_transcriber:
    transcription_widget(key_suffix="_comment", compact_mode=True)


# ── CSV Upload ────────────────────────────────────────────────────────────────
exp_csv = st.expander("CSV Upload")

with exp_csv:
    st.caption(
        "Upload a CSV (no header row) with three columns: "
        "**ISO 8601 timestamp** · **log text** (plain text or Markdown) · **initials**\n\n"
        "Example row: `2026-03-23T14:05:00,Sample was prepared,ljf`"
    )
    uploaded_file = st.file_uploader("Choose CSV file", type="csv", key="csv_upload")

    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file, header=None, dtype=str)
        except Exception as e:
            st.error(f"Could not read CSV: {e}")
            st.stop()

        if df.shape[1] != 3:
            st.error(f"CSV must have exactly 3 columns (found {df.shape[1]}): ISO timestamp, log text, initials.")
        else:
            df.columns = ['timestamp', 'log', 'initials']
            valid_rows, errors = [], []

            for i, row in df.iterrows():
                ts_str  = str(row['timestamp']).strip()
                log_str = str(row['log']).strip()
                ini_str = str(row['initials']).strip()

                try:
                    datetime.datetime.fromisoformat(ts_str)
                except ValueError:
                    errors.append(f"Row {i+1}: invalid ISO 8601 timestamp '{ts_str}'")
                    continue
                if not log_str:
                    errors.append(f"Row {i+1}: log text is empty")
                    continue
                if not is_valid_short_name(ini_str) or len(ini_str) > 6:
                    errors.append(
                        f"Row {i+1}: invalid initials '{ini_str}' "
                        "(lowercase letters/digits/underscores, max 6 chars, must start with a letter)"
                    )
                    continue
                valid_rows.append((ts_str, md.markdown(log_str), ini_str))

            for err in errors:
                st.warning(err)

            if valid_rows:
                st.write(
                    f"**{len(valid_rows)} valid rows** found"
                    + (f", {len(errors)} row(s) skipped due to errors." if errors else ".")
                )
                st.dataframe(
                    pd.DataFrame(valid_rows, columns=["Timestamp", "Log", "Initials"]),
                    use_container_width=True,
                )
                if st.button("Upload to elabFTW", type="primary", key="csv_confirm"):
                    entity_type = st.session_state.get('entity_type', 'experiments')
                    inserted, skipped = bulk_append_to_experiment(
                        st.session_state.api_client, st.session_state.exp_id,
                        valid_rows, entity_type=entity_type,
                    )
                    st.success(f"Done! {inserted} row(s) inserted, {skipped} exact duplicate(s) skipped.")
            elif not errors:
                st.warning("No valid rows found in the CSV.")


# ── Session log ───────────────────────────────────────────────────────────────
session_log = st.session_state.get('session_log', [])

if session_log:
    st.divider()
    st.subheader("Session History")

    # Group by experiment/resource, preserving insertion order
    seen_names = []
    groups = {}
    for entry in session_log:
        name = entry['exp_name']
        if name not in groups:
            groups[name] = {'entity_type': entry['entity_type'], 'rows': []}
            seen_names.append(name)
        groups[name]['rows'].append(entry)

    for name in seen_names:
        g = groups[name]
        label = 'Resource' if g['entity_type'] == 'items' else 'Experiment'
        st.markdown(f"**{label}: {name}**")
        st.dataframe(
            pd.DataFrame(
                [{'ISO time': e['timestamp'], 'Log': e['content'], 'Initials': e['initials']}
                 for e in g['rows']],
            ),
            use_container_width=True,
            hide_index=True,
        )
