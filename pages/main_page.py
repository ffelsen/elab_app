import io
import re
import zipfile
import streamlit as st
import elabapi_python
import datetime
import json
import os
from utils import (
    get_experiments, get_items, build_log_table, parse_log_rows,
    get_exp_info, check_log_compatibility, bulk_append_to_experiment,
    _find_all_log_tables,
)
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


@st.dialog('Download logs by timespan', width='large')
def download_timespan_dialog():
    """Zip all entries, trimming log tables to a chosen date range, and save directly."""
    today = datetime.date.today()

    # ── Mode selector ──────────────────────────────────────────────────────────
    mode = st.radio('Date range', ['Single day', 'Span of days'], horizontal=True)

    # ── Date selection ─────────────────────────────────────────────────────────
    if mode == 'Single day':
        from_date = st.date_input('Date', value=today, format='YYYY-MM-DD')
        to_date = from_date
    else:
        col_f, col_t = st.columns(2)
        from_date = col_f.date_input('From', value=today, format='YYYY-MM-DD')
        to_date   = col_t.date_input('To',   value=today, format='YYYY-MM-DD')

    # ── Save path ──────────────────────────────────────────────────────────────
    if from_date == to_date:
        default_name = f'elab_logs_{from_date}.zip'
    else:
        default_name = f'elab_logs_{from_date}_{to_date}.zip'
    save_path = st.text_input(
        'Save to',
        value=os.path.join(os.path.expanduser('~'), 'Downloads', default_name),
    )

    if not st.button('Create zip & save', type='primary', use_container_width=True):
        return

    # ── Validate ───────────────────────────────────────────────────────────────
    if from_date > to_date:
        st.error('"From" date must be on or before "to" date.')
        return

    api_client = st.session_state.api_client

    try:
        exp_names, exp_ids, exp_entries = get_experiments(api_client)
    except Exception as exc:
        st.error(f'Could not fetch experiments: {exc}')
        return
    try:
        item_names, item_ids, item_entries = get_items(api_client)
    except Exception as exc:
        st.error(f'Could not fetch resources: {exc}')
        return

    total = len(exp_entries) + len(item_entries)
    if total == 0:
        st.warning('No entries found.')
        return

    progress = st.progress(0, text='Starting…')
    buf = io.BytesIO()
    included = 0
    skipped_no_table = 0
    skipped_no_rows = 0
    errors = []

    def _trim_body(html, filtered_rows):
        """Replace every log table in html with a table containing only filtered_rows."""
        tables = _find_all_log_tables(html)
        if not tables:
            return html
        new_table = build_log_table(filtered_rows)
        first_s, first_e = tables[0]
        parts = [html[:first_s], new_table]
        prev = first_e
        for s, e in tables[1:]:
            parts.append(html[prev:s])
            prev = e
        parts.append(html[prev:])
        return ''.join(parts)

    def _add_entry(zf, name, eid, folder, fetch_fn, prog_idx):
        nonlocal included, skipped_no_table, skipped_no_rows
        progress.progress((prog_idx + 1) / total, text=f'Processing: {name}')
        try:
            data = fetch_fn(eid)
            payload = api_client.sanitize_for_serialization(data)

            # Find which body field(s) contain log tables — check both 'body' and 'body_html'
            body_keys_with_tables = [
                k for k in ('body', 'body_html')
                if k in payload and _find_all_log_tables(payload.get(k) or '')
            ]
            if not body_keys_with_tables:
                skipped_no_table += 1
                return

            # Use the first field found to parse rows (they should be identical)
            primary_key = body_keys_with_tables[0]
            primary_body = payload[primary_key] or ''
            primary_tables = _find_all_log_tables(primary_body)
            all_rows = []
            for s, e in primary_tables:
                all_rows.extend(parse_log_rows(primary_body[s:e]))

            filtered = []
            for row in all_rows:
                try:
                    row_date = datetime.datetime.fromisoformat(row[0]).date()
                    if from_date <= row_date <= to_date:
                        filtered.append(row)
                except (ValueError, TypeError):
                    pass

            if not filtered:
                skipped_no_rows += 1
                return

            # Trim every body field that has log tables
            for k in body_keys_with_tables:
                payload[k] = _trim_body(payload[k] or '', filtered)

            safe = re.sub(r'[\\/:*?"<>|]', '_', name)[:80]
            zf.writestr(
                f'{safe}_{eid}.json',
                json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            )
            included += 1
        except Exception as exc:
            errors.append(f'**{name}** ({folder}/{eid}): `{type(exc).__name__}: {exc}`')

    exp_api  = elabapi_python.ExperimentsApi(api_client)
    item_api = elabapi_python.ItemsApi(api_client)

    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for i, (name, eid) in enumerate(zip(exp_names, exp_ids)):
            _add_entry(zf, name, eid, 'experiments', exp_api.get_experiment, i)
        for i, (name, eid) in enumerate(zip(item_names, item_ids)):
            _add_entry(zf, name, eid, 'resources', item_api.get_item, len(exp_entries) + i)

    progress.progress(1.0, text='Done!')

    # ── Diagnostics ───────────────────────────────────────────────────────────
    if errors:
        with st.expander(f'⚠️ {len(errors)} entries could not be fetched (click to expand)'):
            for msg in errors:
                st.markdown(f'- {msg}')
    if skipped_no_table or skipped_no_rows:
        st.caption(
            f'{skipped_no_table} had no log table · '
            f'{skipped_no_rows} had no rows in range · '
            f'{included} included'
        )

    if included == 0:
        st.warning('No entries had log rows in the selected date range.')
        return

    # ── Save directly (no rerun — keeps the dialog open) ──────────────────────
    try:
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        with open(save_path, 'wb') as fh:
            fh.write(buf.getvalue())
        st.success(f'✅ Saved {included} entr{"y" if included == 1 else "ies"} to `{save_path}`')
    except Exception as exc:
        st.error(f'Could not save file: {exc}')


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
    st.session_state['all_items'] = [
        {'name': n, 'id': i, 'type': 'items'} for n, i in zip(names, ids)
    ]
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
                         url='https://eln.ub.tum.de/%s?mode=view&id=%i' % (page_base, exp_id),
                         use_container_width=True)
    if col_dl.button('Download elabFTW entry', use_container_width=True):
        download_dialog(exp_id, exp_name, entity_type)

    if st.button('Download all logs during timespan', use_container_width=True):
        download_timespan_dialog()

    entry = entries[names.index(exp_name)]
    st.markdown(get_exp_info(st.session_state.api_client, entry))

    # ── elab-app log compatibility check ─────────────────────────────────────
    compat = check_log_compatibility(entry.body)

    if compat['status'] == 'no_table':
        st.info(
            "ℹ️ No elab-app log table yet — one will be created automatically when you post your first log."
        )

    elif compat['status'] == 'ok':
        st.success(
            f"✅ elab-app log table found — "
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
            f"⚠️ elab-app log found — "
            f"{len(compat['rows'])} row(s), all valid, but: " + "; ".join(detail) + "."
        )
        st.info(
            "You can fix the order by uploading a one-line CSV on the **Add text logs** page "
            "(CSV Upload section). Copy the line below:"
        )
        st.code(f'{now_iso},reordered table according to timestamp,{initials}', language='text')
        if st.button("Fix order now", type="primary", key="fix_order_btn"):
            reorder_row = (now_iso, 'reordered table according to timestamp', initials, LOG_SCHEMA_VERSION)
            bulk_append_to_experiment(
                st.session_state.api_client, exp_id, [reorder_row], entity_type=entity_type,
            )
            st.success("✅ Table reordered! Reload the page to confirm.")

    else:  # 'warnings'
        n_ok = len(compat['rows']) - len(compat['bad_rows'])
        st.warning(
            f"⚠️ elab-app log table found — "
            f"{len(compat['rows'])} row(s), {n_ok} valid, {len(compat['bad_rows'])} with issues:"
        )
        for idx, row, reason in compat['bad_rows']:
            st.markdown(f"- **Row {idx}** (`{row[0]}` / `{row[2]}`): {reason}")
