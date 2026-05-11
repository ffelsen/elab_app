import io
import re
import zipfile
import tempfile
import datetime
import json
import os
import tomllib
from pathlib import Path
from uuid import uuid4
from warnings import filterwarnings

import markdown as md_lib
import pandas as pd
import streamlit as st
import elabapi_python
from PIL import Image
from platformdirs import user_config_dir
from streamlit_drawable_canvas import st_canvas

from utils import (
    get_experiments, get_items, build_log_table, parse_log_rows,
    get_exp_info, check_log_compatibility, bulk_append_to_experiment,
    _find_all_log_tables, append_to_experiment, upload_image, insert_image,
)
from version import LOG_SCHEMA_VERSION
from auth import is_valid_short_name, ELAB_HOST
from components.hashtag_textarea import hashtag_textarea
import pages.templates as templates
from pages.create_transcript import transcription_widget

filterwarnings('ignore')

_TEMP_DIR = Path(tempfile.gettempdir()) / "elab_app"
_TEMP_DIR.mkdir(exist_ok=True)

_BASE_URL = ELAB_HOST.replace('/api/v2', '')


def _get_elab_base_url() -> str:
    cfg_file = Path(user_config_dir("elab_app")) / "config.toml"
    default = "https://eln.ub.tum.de/api/v2"
    if cfg_file.exists():
        with open(cfg_file, "rb") as f:
            host = tomllib.load(f).get("elab_host", default)
    else:
        host = default
    return host.replace("/api/v2", "")


# ── Download dialogs ───────────────────────────────────────────────────────────

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
    mode = st.radio('Date range', ['Single day', 'Span of days'], horizontal=True)
    if mode == 'Single day':
        from_date = st.date_input('Date', value=today, format='YYYY-MM-DD')
        to_date = from_date
    else:
        col_f, col_t = st.columns(2)
        from_date = col_f.date_input('From', value=today, format='YYYY-MM-DD')
        to_date   = col_t.date_input('To',   value=today, format='YYYY-MM-DD')

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
    included = skipped_no_table = skipped_no_rows = 0
    errors = []

    def _trim_body(html, filtered_rows):
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
            body_keys_with_tables = [
                k for k in ('body', 'body_html')
                if k in payload and _find_all_log_tables(payload.get(k) or '')
            ]
            if not body_keys_with_tables:
                skipped_no_table += 1
                return
            primary_key = body_keys_with_tables[0]
            primary_body = payload[primary_key] or ''
            all_rows = []
            for s, e in _find_all_log_tables(primary_body):
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
    try:
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        with open(save_path, 'wb') as fh:
            fh.write(buf.getvalue())
        st.success(f'✅ Saved {included} entr{"y" if included == 1 else "ies"} to `{save_path}`')
    except Exception as exc:
        st.error(f'Could not save file: {exc}')


# ── Page ───────────────────────────────────────────────────────────────────────

# Tab bar styling
st.markdown("""
<style>
/* Coloured background on the tab bar to visually anchor the right panel */
div[data-testid="stTabBar"],
div[data-testid="tabs-bounding-box"] {
    background-color: rgba(49, 51, 63, 0.06);
    border-radius: 6px;
    padding: 3px 6px;
}
</style>
""", unsafe_allow_html=True)

col_open, col_sep, col_input = st.columns([2, 0.04, 3])

# ══ LEFT: Select entry ═════════════════════════════════════════════════════════
with col_open:
    _options = ['experiments', 'items']
    _saved_type = st.session_state.get('entity_type', 'experiments')
    _default_type = _options.index(_saved_type) if _saved_type in _options else 0
    entity_type = st.radio(
        'Entry type',
        options=_options,
        format_func=lambda x: 'Experiment' if x == 'experiments' else 'Resource',
        horizontal=True,
        index=_default_type,
        label_visibility='collapsed',
    )
    st.session_state['entity_type'] = entity_type

    if entity_type == 'experiments':
        names, ids, entries = get_experiments(st.session_state.api_client)
        page_base = 'experiments.php'
        try:
            _r_names, _r_ids, _ = get_items(st.session_state.api_client)
        except Exception:
            _r_names, _r_ids = [], []
        st.session_state['all_items'] = (
            [{'name': n, 'id': i, 'type': 'experiments'} for n, i in zip(names, ids)] +
            [{'name': n, 'id': i, 'type': 'items'}       for n, i in zip(_r_names, _r_ids)]
        )
    else:
        names, ids, entries = get_items(st.session_state.api_client)
        page_base = 'database.php'
        try:
            _e_names, _e_ids, _ = get_experiments(st.session_state.api_client)
        except Exception:
            _e_names, _e_ids = [], []
        st.session_state['all_items'] = (
            [{'name': n, 'id': i, 'type': 'items'}       for n, i in zip(names, ids)] +
            [{'name': n, 'id': i, 'type': 'experiments'} for n, i in zip(_e_names, _e_ids)]
        )

    if not names:
        entry_label = 'experiment' if entity_type == 'experiments' else 'resource'
        st.write('No %ss available. Create a new %s first!' % (entry_label, entry_label))
    else:
        saved_name = st.session_state.get('exp_name', '')
        default_index = names.index(saved_name) if saved_name in names else 0
        exp_name = st.selectbox(
            'Entry title', names, index=default_index, label_visibility='collapsed',
        )
        exp_id = ids[names.index(exp_name)]

        # Detect selection change so the header bar in main.py (which runs before
        # this page script) reflects the new entry on the very same interaction.
        _changed = (exp_id != st.session_state.get('exp_id') or
                    entity_type != st.session_state.get('entity_type'))
        st.session_state['exp_name'] = exp_name
        st.session_state['exp_id'] = exp_id
        if _changed:
            st.rerun()

        col_link, col_dl = st.columns(2)
        col_link.link_button(
            'Open in elabFTW',
            url='%s/%s?mode=view&id=%i' % (_get_elab_base_url(), page_base, exp_id),
            use_container_width=True,
        )
        if col_dl.button('Download entry', use_container_width=True):
            download_dialog(exp_id, exp_name, entity_type)

        if st.button('Download all logs during timespan', use_container_width=True):
            download_timespan_dialog()

        entry = entries[names.index(exp_name)]

        # ── Compatibility check ────────────────────────────────────────────────
        compat = check_log_compatibility(entry.body)

        if compat['status'] == 'no_table':
            st.info(
                "ℹ️ No elab-app log table yet — one will be created automatically "
                "when you post your first log."
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
            st.info("You can fix the order by uploading a one-line CSV on the CSV tab. Copy the line below:")
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


# ── Separator column ──────────────────────────────────────────────────────────
with col_sep:
    st.markdown(
        '<div style="border-left:1px solid rgba(128,128,128,0.3);'
        'height:calc(100vh - 200px);width:1px;margin:0 auto;pointer-events:none;"></div>',
        unsafe_allow_html=True,
    )

# ══ RIGHT: Input tabs ══════════════════════════════════════════════════════════
with col_input:
    if not st.session_state.get('exp_id'):
        st.info("ℹ️ Select an experiment or resource on the left to start logging.")
    else:
        tab_chat, tab_template, tab_voice, tab_csv, tab_sketch = st.tabs([
            "💬 Chat", "📋 Template", "🎤 Voice", "📄 CSV", "✏️ Sketch",
        ])

        # ── Chat ──────────────────────────────────────────────────────────────
        with tab_chat:
            if 'all_items' not in st.session_state:
                try:
                    _rn, _ri, _ = get_items(st.session_state.api_client)
                    _r = [{'name': n, 'id': i, 'type': 'items'} for n, i in zip(_rn, _ri)]
                except Exception:
                    _r = []
                try:
                    _en, _ei, _ = get_experiments(st.session_state.api_client)
                    _e = [{'name': n, 'id': i, 'type': 'experiments'} for n, i in zip(_en, _ei)]
                except Exception:
                    _e = []
                st.session_state['all_items'] = _r + _e

            if 'chat_reset_key' not in st.session_state:
                st.session_state['chat_reset_key'] = 0

            result = hashtag_textarea(
                items=st.session_state['all_items'],
                base_url=_BASE_URL,
                placeholder="Add a comment… (type # to link a resource or experiment, Ctrl+Enter to submit)",
                reset_key=st.session_state['chat_reset_key'],
                key="chat_hashtag_ta",
            )

            if result and result.get('submitted') and result.get('text', '').strip():
                ok = append_to_experiment(
                    st.session_state.api_client,
                    st.session_state.exp_id,
                    result['text'].strip(),
                    entity_type=st.session_state.get('entity_type', 'experiments'),
                    initials=st.session_state.get('initials', ''),
                )
                if ok:
                    st.success("✅ Comment added.")
                else:
                    st.error("⚠️ Could not send to elabFTW — see **Session History** below.")
                st.session_state.pop('chat_hashtag_ta', None)
                st.session_state['chat_reset_key'] += 1
                st.rerun()

        # ── Template ──────────────────────────────────────────────────────────
        with tab_template:
            _py_templates   = templates.PYTHON_TEMPLATES
            _yaml_templates = templates.load_yaml_templates()
            _all_options    = ['Choose a template'] + list(_py_templates.keys()) + list(_yaml_templates.keys())
            temp = st.selectbox('Choose a template', _all_options, key='selection')
            if temp != 'Choose a template':
                if temp in _yaml_templates:
                    templates.yaml_template_dialog(_yaml_templates[temp])
                else:
                    _py_templates[temp]()

        # ── Voice ─────────────────────────────────────────────────────────────
        with tab_voice:
            transcription_widget(key_suffix="_main", compact_mode=True)

        # ── CSV ───────────────────────────────────────────────────────────────
        with tab_csv:
            st.caption(
                "Upload a CSV (no header row) with three columns: "
                "**ISO 8601 timestamp** · **log text** (plain text or Markdown) · **initials**\n\n"
                "Example row: `2026-03-23T14:05:00,Sample was prepared,ljf`"
            )
            uploaded_file = st.file_uploader("Choose CSV file", type="csv", key="csv_upload")

            if uploaded_file is not None:
                try:
                    df_csv = pd.read_csv(uploaded_file, header=None, dtype=str)
                except Exception as e:
                    st.error(f"Could not read CSV: {e}")
                    st.stop()

                if df_csv.shape[1] != 3:
                    st.error(f"CSV must have exactly 3 columns (found {df_csv.shape[1]}): ISO timestamp, log text, initials.")
                else:
                    df_csv.columns = ['timestamp', 'log', 'initials']
                    valid_rows, errors = [], []

                    for row_num, (_, row) in enumerate(df_csv.iterrows(), start=1):
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
                        valid_rows.append((ts_str, md_lib.markdown(log_str), ini_str, LOG_SCHEMA_VERSION))

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
                            inserted, skipped, err = bulk_append_to_experiment(
                                st.session_state.api_client,
                                st.session_state.exp_id,
                                valid_rows,
                                entity_type=st.session_state.get('entity_type', 'experiments'),
                            )
                            if err:
                                st.error(f"⚠️ Upload failed: {err}\n\nFailed rows appear in **Session History** below.")
                            else:
                                st.success(f"Done! {inserted} row(s) inserted, {skipped} exact duplicate(s) skipped.")
                    elif not errors:
                        st.warning("No valid rows found in the CSV.")

        # ── Sketch ────────────────────────────────────────────────────────────
        with tab_sketch:
            # Tool controls in a horizontal row above the canvas.
            # (Nested columns inside tabs inside columns caused click-blocking
            # with the st_canvas iframe; a flat layout avoids that.)
            sk_c1, sk_c2, sk_c3, sk_c4 = st.columns([2, 1, 1, 2])
            drawing_mode = sk_c1.selectbox(
                "Tool",
                ("freedraw", "line", "rect", "circle", "transform", "polygon", "point"),
                key="sketch_mode",
            )
            stroke_width = sk_c2.slider("Stroke width", 1, 25, 3, key="sketch_stroke_w")
            point_display_radius = (
                sk_c3.slider("Point radius", 1, 25, 3, key="sketch_point_r")
                if drawing_mode == "point" else 0
            )
            sk_c4_inner_a, sk_c4_inner_b = sk_c4.columns(2)
            stroke_color = sk_c4_inner_a.color_picker("Stroke", "#000000", key="sketch_stroke_c")
            bg_color     = sk_c4_inner_b.color_picker("Background", "#eeeeee", key="sketch_bg_c")

            sk_img_col, sk_rt_col = st.columns([3, 1])
            bg_image_file   = sk_img_col.file_uploader("Background image", type=["png", "jpg"], key="sketch_bg_img")
            realtime_update = sk_rt_col.checkbox("Realtime update", True, key="sketch_realtime")

            canvas_result = st_canvas(
                fill_color="rgba(255, 165, 0, 0.3)",
                stroke_width=stroke_width,
                stroke_color=stroke_color,
                background_color=bg_color,
                background_image=Image.open(bg_image_file) if bg_image_file else None,
                update_streamlit=realtime_update,
                height=400,
                drawing_mode=drawing_mode,
                point_display_radius=point_display_radius,
                display_toolbar=True,
                key="sketch_canvas",
            )

            if st.button('Upload drawing', key="sketch_upload"):
                iid = uuid4()
                im = Image.fromarray(canvas_result.image_data)
                file_path = _TEMP_DIR / f"{iid}.png"
                im.save(file_path, "PNG")
                sketch_entity_type = st.session_state.get('entity_type', 'experiments')
                sketch_initials    = st.session_state.get('initials', '')
                try:
                    upload_image(
                        st.session_state.api_client,
                        st.session_state.exp_id,
                        str(file_path),
                        entity_type=sketch_entity_type,
                    )
                except Exception as exc:
                    st.error(f"⚠️ Could not upload image to elabFTW: {exc}")
                else:
                    ok = insert_image(
                        st.session_state.api_client,
                        st.session_state.exp_id,
                        file_path.name,
                        entity_type=sketch_entity_type,
                        initials=sketch_initials,
                    )
                    if ok:
                        st.success("✅ Drawing uploaded and logged!")
                    else:
                        st.error("⚠️ Image uploaded but could not write log entry — see **Session History** below.")


# ══ Session History (full width) ═══════════════════════════════════════════════

session_log = st.session_state.get('session_log', [])

if session_log:
    st.divider()
    n_failed = sum(1 for e in session_log if e.get('failed'))
    header = "Session History (newest first)"
    if n_failed:
        header += f" — ⚠️ {n_failed} failed"
    st.subheader(header)

    reversed_log = list(reversed(session_log))
    df_rows = []
    for e in reversed_log:
        entry_label = 'Resource' if e['entity_type'] == 'items' else 'Experiment'
        df_rows.append({
            'Entry':    f"{entry_label}: {e['exp_name']}",
            'ISO time': e['timestamp'],
            'Log':      e['content'],
            'Initials': e['initials'],
        })
    df = pd.DataFrame(df_rows)

    row_failed = [e.get('failed', False) for e in reversed_log]
    def _style_rows(row, _flags=row_failed):
        if _flags[row.name]:
            return ['background-color: #ffd6d6; color: #7a0000'] * len(row)
        return [''] * len(row)

    st.dataframe(df.style.apply(_style_rows, axis=1),
                 use_container_width=True, hide_index=True)

    failed_entries = [(i, e) for i, e in enumerate(session_log) if e.get('failed')]
    if failed_entries:
        with st.expander(f"⚠️ {len(failed_entries)} failed entr{'y' if len(failed_entries)==1 else 'ies'} — click to re-send or copy"):
            for i, e in failed_entries:
                entry_label = 'Resource' if e['entity_type'] == 'items' else 'Experiment'
                st.markdown(
                    f"**{entry_label}: {e['exp_name']}** · {e['timestamp']}  \n"
                    f"`{e.get('error', 'unknown error')}`"
                )
                st.code(e['content'], language=None)
                col_r, _ = st.columns([1, 4])
                if col_r.button("↩ Re-send", key=f"resend_{i}"):
                    ok = append_to_experiment(
                        st.session_state.api_client,
                        e['exp_id'],
                        e['content'],
                        custom_timestamp=e['timestamp'],
                        entity_type=e['entity_type'],
                        initials=e['initials'],
                    )
                    if ok:
                        e['failed'] = False
                        e['error'] = None
                        if st.session_state['session_log'][-1].get('failed') is False:
                            st.session_state['session_log'].pop()
                        st.rerun()
                    else:
                        st.session_state['session_log'].pop()
                        st.error("Still failing — check elabFTW permissions.")
