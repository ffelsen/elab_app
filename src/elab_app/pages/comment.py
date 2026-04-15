import streamlit as st
import pandas as pd
import datetime
from warnings import filterwarnings
from utils import get_items, append_to_experiment, bulk_append_to_experiment
from version import LOG_SCHEMA_VERSION
import markdown as md
import pages.templates as templates
from pages.create_transcript import transcription_widget
from auth import is_valid_short_name, ELAB_HOST
from components.hashtag_textarea import hashtag_textarea

_BASE_URL = ELAB_HOST.replace('/api/v2', '')

filterwarnings('ignore')

st.title("eLabFTW Log")
st.header('Add a comment to the notebook')


# ── Chat mode ─────────────────────────────────────────────────────────────────
exp_chat = st.expander("Chat mode")

with exp_chat:
    # Reuse items list cached by main_page; fallback-fetch if missing
    if 'all_items' not in st.session_state:
        try:
            _names, _ids, _ = get_items(st.session_state.api_client)
            st.session_state['all_items'] = [
                {'name': n, 'id': i, 'type': 'items'} for n, i in zip(_names, _ids)
            ]
        except Exception:
            st.session_state['all_items'] = []

    if 'chat_reset_key' not in st.session_state:
        st.session_state['chat_reset_key'] = 0

    result = hashtag_textarea(
        items=st.session_state['all_items'],
        base_url=_BASE_URL,
        placeholder="Add a comment… (type # to link a resource, Ctrl+Enter to submit)",
        reset_key=st.session_state['chat_reset_key'],
        key="chat_hashtag_ta",
    )

    if result and result.get('submitted') and result.get('text', '').strip():
        entity_type = st.session_state.get('entity_type', 'experiments')
        ok = append_to_experiment(
            st.session_state.api_client, st.session_state.exp_id,
            result['text'].strip(),
            entity_type=entity_type,
            initials=st.session_state.get('initials', ''),
        )
        if ok:
            st.success("✅ Comment added.")
        else:
            st.error("⚠️ Could not send to elabFTW — see **Session History** below for details and re-send options.")
        st.session_state.pop('chat_hashtag_ta', None)
        st.session_state['chat_reset_key'] += 1
        st.rerun()


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

            for row_num, (_, row) in enumerate(df.iterrows(), start=1):
                ts_str  = str(row['timestamp']).strip()
                log_str = str(row['log']).strip()
                ini_str = str(row['initials']).strip()

                try:
                    datetime.datetime.fromisoformat(ts_str)
                except ValueError:
                    errors.append(f"Row {row_num}: invalid ISO 8601 timestamp '{ts_str}'")
                    continue
                if not log_str:
                    errors.append(f"Row {row_num}: log text is empty")
                    continue
                if not is_valid_short_name(ini_str) or len(ini_str) > 6:
                    errors.append(
                        f"Row {row_num}: invalid initials '{ini_str}' "
                        "(lowercase letters/digits/underscores, max 6 chars, must start with a letter)"
                    )
                    continue
                valid_rows.append((ts_str, md.markdown(log_str), ini_str, LOG_SCHEMA_VERSION))

            for err in errors:
                st.warning(err)

            if valid_rows:
                st.write(
                    f"**{len(valid_rows)} valid rows** found"
                    + (f", {len(errors)} row(s) skipped due to errors." if errors else ".")
                )
                st.dataframe(
                    pd.DataFrame(valid_rows, columns=pd.Index(["Timestamp", "Log", "Initials", "App version"])),
                    use_container_width=True,
                )
                if st.button("Upload to elabFTW", type="primary", key="csv_confirm"):
                    entity_type = st.session_state.get('entity_type', 'experiments')
                    inserted, skipped, err = bulk_append_to_experiment(
                        st.session_state.api_client, st.session_state.exp_id,
                        valid_rows, entity_type=entity_type,
                    )
                    if err:
                        st.error(f"⚠️ Upload failed: {err}\n\nFailed rows appear in **Session History** below.")
                    else:
                        st.success(f"Done! {inserted} row(s) inserted, {skipped} exact duplicate(s) skipped.")
            elif not errors:
                st.warning("No valid rows found in the CSV.")


# ── Session log ───────────────────────────────────────────────────────────────
session_log = st.session_state.get('session_log', [])

if session_log:
    st.divider()
    n_failed = sum(1 for e in session_log if e.get('failed'))
    header = "Session History"
    if n_failed:
        header += f" — ⚠️ {n_failed} failed"
    st.subheader(header)

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

        df_rows = [{'ISO time': e['timestamp'], 'Log': e['content'], 'Initials': e['initials']}
                   for e in g['rows']]
        df = pd.DataFrame(df_rows)

        # Colour failed rows red using pandas Styler
        row_failed = [e.get('failed', False) for e in g['rows']]
        def _style_rows(row, _flags=row_failed):
            if _flags[row.name]:
                return ['background-color: #ffd6d6; color: #7a0000'] * len(row)
            return [''] * len(row)

        st.dataframe(df.style.apply(_style_rows, axis=1),
                     use_container_width=True, hide_index=True)

        # Re-send panel for failed entries
        failed_in_group = [(i, e) for i, e in enumerate(g['rows']) if e.get('failed')]
        if failed_in_group:
            with st.expander(f"⚠️ {len(failed_in_group)} failed entr{'y' if len(failed_in_group)==1 else 'ies'} — click to re-send or copy"):
                for i, e in failed_in_group:
                    st.markdown(f"**{e['timestamp']}**  \n`{e.get('error', 'unknown error')}`")
                    st.code(e['content'], language=None)
                    col_r, col_s = st.columns([1, 4])
                    if col_r.button("↩ Re-send", key=f"resend_{name}_{i}"):
                        ok = append_to_experiment(
                            st.session_state.api_client,
                            e['exp_id'],
                            e['content'],
                            custom_timestamp=e['timestamp'],
                            entity_type=e['entity_type'],
                            initials=e['initials'],
                        )
                        if ok:
                            # mark original entry as resolved and remove the duplicate just added
                            e['failed'] = False
                            e['error'] = None
                            # remove the re-send duplicate from session_log
                            if st.session_state['session_log'][-1].get('failed') is False:
                                st.session_state['session_log'].pop()
                            st.rerun()
                        else:
                            # remove the duplicate failed entry just added by append_to_experiment
                            st.session_state['session_log'].pop()
                            st.error("Still failing — check elabFTW permissions.")
