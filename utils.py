import re
import streamlit as st
from version import LOG_SCHEMA_VERSION, LOG_SCHEMA_APP, LOG_SCHEMA_URL
import numpy as np
import pandas as pd
from datetime import date
import calendar
import elabapi_python
from elabapi_python.rest import ApiException
from warnings import filterwarnings
import datetime
from PIL import Image
from uuid import uuid4
import markdown as md
from utils import *

def append_to_experiment_old(api_client, exp_id, content):
    """Append a time stamped comment to an ElabFTW entry

    Keyword arguments:
    api_client -- elabapi_python api_client instance
    exp_id -- id of the elab entry of the experiment
    content -- content to add to the line (str)
    """
    now = datetime.datetime.now()
    content = ': '.join([now.strftime("%Y-%m-%d_%H-%M-%S"),content]) # add time stamp
    content = content.replace('\n','<br>') # add line break
    
    # get current content of the experiment
    names, ids, exps = get_experiments(api_client)
    ind = ids.index(exp_id)
    current_content = exps[ind].body
    
    # add new content
    new_content = '<br>'.join([current_content,content])

    # initialize experiments api
    experimentsApi = elabapi_python.ExperimentsApi(api_client)
    # upload new content
    experimentsApi.patch_experiment(exp_id,body={'body':new_content})
    return True

def append_to_experiment(api_client, exp_id, content, custom_timestamp=None, entity_type='experiments', initials=''):
    """Append a time stamped comment to an ElabFTW entry
    in a tabular format

    Keyword arguments:
    api_client -- elabapi_python api_client instance
    exp_id -- id of the elab entry of the experiment or item
    content -- content to add to the line (str)
    custom_timestamp -- optional custom timestamp string (if None, uses current time)
    entity_type -- 'experiments' or 'items' (default: 'experiments')
    initials -- user initials to record in the third column (default: '')
    """

    # Use custom timestamp if provided, otherwise use current time
    if custom_timestamp is not None:
        timestamp = custom_timestamp
    else:
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y-%m-%dT%H:%M:%S")

    content_plain = content                 # keep original for session log
    content_html  = md.markdown(content)

    # get current content of the entry
    if entity_type == 'items':
        names, ids, entries = get_items(api_client)
    else:
        names, ids, entries = get_experiments(api_client)
    current_content = entries[ids.index(exp_id)].body or ''

    new_row = (timestamp, content_html, initials)
    new_content, inserted, skipped, n_tables = _consolidate(current_content, [new_row])

    # patch the entry
    if entity_type == 'items':
        elabapi_python.ItemsApi(api_client).patch_item(exp_id, body={'body': new_content})
    else:
        elabapi_python.ExperimentsApi(api_client).patch_experiment(exp_id, body={'body': new_content})

    # count total rows in the updated table for the session log
    all_tables = _find_all_log_tables(new_content)
    total_rows = sum(len(parse_log_rows(new_content[s:e])) for s, e in all_tables
                     if _extract_table_version(new_content[s:e]) == LOG_SCHEMA_VERSION)

    # append to session log so the comment page can display it centrally
    if 'session_log' not in st.session_state:
        st.session_state['session_log'] = []
    st.session_state['session_log'].append({
        'exp_name':   st.session_state.get('exp_name', str(exp_id)),
        'entity_type': entity_type,
        'timestamp':  timestamp,
        'content':    content_plain,
        'initials':   initials,
        'n_tables':   n_tables,
        'total_rows': total_rows,
    })

def upload_image(api_client, exp_id, path, entity_type='experiments'):
    """upload image to an experiment or item entry

    Keyword arguments:
    api_client -- elabapi_python api_client instance
    exp_id -- id of the elab entry of the experiment or item
    path -- path of the image file to upload (str)
    entity_type -- 'experiments' or 'items' (default: 'experiments')
    """
    uploadsApi = elabapi_python.UploadsApi(api_client)

    img = Image.open(path)
    size = img.size
    uploadsApi.post_upload(entity_type, exp_id, file=path, comment='%i:%i'%size)
    return True

def get_uploads(api_client, exp_id, entity_type='experiments'):
    """read all uploads connected to an experiment or item

    Keyword arguments:
    api_client -- elabapi_python api_client instance
    exp_id -- id of the elab entry of the experiment or item
    entity_type -- 'experiments' or 'items' (default: 'experiments')

    Returns:
    names -- names of the uploads
    upls -- list of full upload entries
    """
    uploadsApi = elabapi_python.UploadsApi(api_client)
    upls = uploadsApi.read_uploads(entity_type, exp_id)
    # get the names of the uploads
    names = [up.real_name for up in upls]
    return names, upls

def get_image_content(upl, width=False, height=False):
    """convert uploaded image to html content 
    for the entry
    
    Keyword arguments:
    upl -- upload entry (ontained using get_uploads)
    width -- width of the image in the html
    height -- height of the image in the html

    Returns:
    cont -- content to add to the entry
    """
    fn = upl.real_name
    ln = upl.long_name
    s = upl.storage
    if width == False or height == False:
        width, height = [int(i) for i in upl.comment.split(':')]
    
    src="app/download.php?name=%s&amp;f=%s&amp;storage=%i"%(fn,ln,s)
    cont = '<p><img src="%s" width="%i" height="%i" ></p>'%(src, width, height)
    return cont

def insert_image(api_client, exp_id, name, entity_type='experiments'):
    """insert image into experiment or item entry

    Keyword arguments:
    api_client -- elabapi_python api_client instance
    exp_id -- id of the elab entry of the experiment or item
    name -- name of the uploaded image
    entity_type -- 'experiments' or 'items' (default: 'experiments')
    """
    names, upls = get_uploads(api_client, exp_id, entity_type=entity_type)
    ind = names.index(name)
    cont = get_image_content(upls[ind])
    append_to_experiment(api_client, exp_id, cont, entity_type=entity_type)
    return True

def get_experiments(api_client):
    """read all experiments

    Keyword arguments:
    api_client -- elabapi_python api_client instance

    Returns:
    names -- names of the experiments
    ids -- ids of the experiments
    upls -- list of full experiment entries
    """
    experimentsApi = elabapi_python.ExperimentsApi(api_client)
    uploadsApi = elabapi_python.UploadsApi(api_client)
    exps = experimentsApi.read_experiments()
    # existing ids 
    names = [exp.title for exp in exps]
    ids = [exp.id for exp in exps]
    return names, ids, exps

def get_items(api_client):
    """read all resources (items)

    Keyword arguments:
    api_client -- elabapi_python api_client instance

    Returns:
    names -- names of the items
    ids -- ids of the items
    items -- list of full item entries
    """
    itemsApi = elabapi_python.ItemsApi(api_client)
    items = itemsApi.read_items()
    names = [item.title for item in items]
    ids = [item.id for item in items]
    return names, ids, items

def create_item(api_client, name, comment='', catid=0):
    """create a new resource (item) entry in elab

    Keyword arguments:
    api_client -- elabapi_python api_client instance
    name -- name of the new item
    comment -- comment to add in the first line of the new entry
    catid -- id of the item category (items type)
    """
    itemsApi = elabapi_python.ItemsApi(api_client)
    itemsApi.post_item(body={'category': catid})
    names, ids, items = get_items(api_client)
    item_id = ids[names.index('Untitled')]
    itemsApi.patch_item(item_id, body={'title': name})
    if comment != '':
        itemsApi.patch_item(item_id, body={'body': comment})
    return True

def get_resource_categories(api_client):
    """get all resource categories (items types) available

    Keyword arguments:
    api_client -- elabapi_python api_client instance

    Returns:
    titles -- names of the categories
    ids -- ids of the categories
    """
    iapi = elabapi_python.ItemsTypesApi(api_client)
    cats = iapi.read_items_types()
    return [cat.title for cat in cats], [cat.id for cat in cats]

def create_experiment(api_client, name, comment='', catid = 0):
    """create a new experiment entry in elab

    Keyword arguments:
    api_client -- elabapi_python api_client instance
    name -- name of the new experiment 
    comment -- comment to add in the first line of the new entry
    catid -- id of the experiment category
    """
    experimentsApi = elabapi_python.ExperimentsApi(api_client)
    experimentsApi.post_experiment()
    names, ids, exps = get_experiments(api_client)
    exp_id = ids[names.index('Untitled')]
    experimentsApi.patch_experiment(exp_id, body={'title':name})
    if comment != '':
        experimentsApi.patch_experiment(exp_id, body={'body':comment})
    experimentsApi.patch_experiment(exp_id, body={'category':catid})

    return True

def get_user_id(api_client, fn, ln):
    """get the id of the current user from name

    Keyword arguments:
    api_client -- elabapi_python api_client instance
    fn -- first name
    ln -- last name
   
    Returns:
    u.userid -- id of the user entry 
    """
    uapi = elabapi_python.UsersApi(api_client)
    users = uapi.read_users()
    for u in users:
        if u.fullname == ' '.join([fn,ln]):
            return u.userid
    else:
        print('User %s %s does not exist!'%(fn,ln))
        return None

def get_teams(api_client, userid):
    """get the ids and names of teams the current user 
    is assigned to 
    
    Keyword arguments:
    api_client -- elabapi_python api_client instance
    userid -- id of the user
     
    Returns:
    [t.id for t in u.teams] -- ids of the teams 
    [t.name for t in u.teams] -- names of the teams 
    """
    uapi = elabapi_python.UsersApi(api_client)
    u = uapi.read_user(userid)
    return [t.id for t in u.teams], [t.name for t in u.teams] 

def get_categories(api_client, team_id):
    """get all experiment categories available to 
    a user from name
    
    Keyword arguments:
    api_client -- elabapi_python api_client instance
    fn -- first name
    ln -- last name
     
    Returns:
    titles -- names of the categories
    ids -- ids of the categories
    colors -- colors assigned to the categories 
    """
    
    eapi = elabapi_python.ExperimentsCategoriesApi(api_client)
    cats = eapi.read_team_experiments_categories(team_id)
    return [cat.title for cat in cats],[cat.id for cat in cats],[cat.color for cat in cats]

def get_name(api_client, userid):
    """get user name from id
    
    Keyword arguments:
    api_client -- elabapi_python api_client instance
    fn -- first name
    userid -- id of the user
     
    Returns:
    u.fullname -- name of the user
    """
    uapi = elabapi_python.UsersApi(api_client)
    users = uapi.read_users()
    for u in users:
        if u.userid == userid:
            return u.fullname
    return False

# ── Log-table helpers ─────────────────────────────────────────────────────────
# Detection is signature-based: we look for any <table> that contains the
# distinctive header text "ISO time (ISO 8601)".  elabFTW strips id/class
# attributes on save, so ID-based detection is not reliable.
#
# Each table written by the app starts with an identifier row:
#   elab_app | <repo URL> | <schema version>
# This row survives elabFTW's sanitisation (text content is preserved) and
# lets us distinguish tables written by different schema versions.

_LOG_SIGNATURE = 'ISO time (ISO 8601)'   # present in all elab-app tables
_ROW_RE = re.compile(r'<tr[^>]*>(.*?)</tr>', re.DOTALL | re.IGNORECASE)
_TD_RE  = re.compile(r'<td[^>]*>(.*?)</td>', re.DOTALL | re.IGNORECASE)
_SHORT_NAME_RE = re.compile(r'^[a-z][a-z0-9_]*$')


def _find_all_log_tables(html):
    """Return list of (start, end) for every table containing the log signature."""
    results = []
    pos = 0
    html = html or ''
    while True:
        t_start = html.lower().find('<table', pos)
        if t_start == -1:
            break
        t_end = html.lower().find('</table>', t_start)
        if t_end == -1:
            break
        t_end += len('</table>')
        if _LOG_SIGNATURE in html[t_start:t_end]:
            results.append((t_start, t_end))
        pos = t_end
    return results


def _extract_table_version(table_html):
    """Return the schema version string from the identifier row, or None for legacy tables."""
    for row_match in _ROW_RE.finditer(table_html):
        tds = _TD_RE.findall(row_match.group(1))
        if len(tds) == 3 and tds[0].strip() == LOG_SCHEMA_APP:
            return tds[2].strip()   # e.g. "v2.0"
    return None  # legacy table — no identifier row


def parse_log_rows(html):
    """Extract data rows (timestamp, content, initials) from a log table HTML.

    Skips the identifier row and header rows (which have <th> cells, not <td>).
    Returns a list of (timestamp_str, content_html, initials) tuples.
    """
    rows = []
    for row_match in _ROW_RE.finditer(html or ''):
        tds = _TD_RE.findall(row_match.group(1))
        if len(tds) == 3 and tds[0].strip() != LOG_SCHEMA_APP:
            rows.append((tds[0].strip(), tds[1].strip(), tds[2].strip()))
    return rows


def build_log_table(rows):
    """Build the elab-app log table HTML from a list of rows (newest first).

    rows: list of (timestamp_str, content_html, initials)
    The first row is the identifier row; the second is the column header.
    Note: elabFTW strips custom attributes on save, so we use plain tags.
    """
    id_row = '<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % (
        LOG_SCHEMA_APP, LOG_SCHEMA_URL, LOG_SCHEMA_VERSION)
    header = '<tr><th>ISO time (ISO 8601)</th><th>Log (newest to oldest)</th><th>Initials</th></tr>'
    tr_blocks = [id_row, header]
    for ts, content, initials in rows:
        tr_blocks.append('<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % (ts, content, initials))
    return '<table>\n%s\n</table>' % '\n'.join(tr_blocks)


def _merge_and_sort(existing_rows, new_rows):
    """Add new_rows to existing_rows, skip exact duplicates, sort newest first."""
    existing_set = set(existing_rows)
    inserted = skipped = 0
    for row in new_rows:
        if row in existing_set:
            skipped += 1
        else:
            existing_rows.append(row)
            existing_set.add(row)
            inserted += 1

    def _key(row):
        try:
            return datetime.datetime.fromisoformat(row[0])
        except ValueError:
            return datetime.datetime.min

    existing_rows.sort(key=_key, reverse=True)
    return existing_rows, inserted, skipped


def _consolidate(current_content, new_rows):
    """Merge new_rows into the current-version log table, sort, return
    (new_full_content, inserted, skipped).

    Only tables matching LOG_SCHEMA_VERSION are merged. Tables with a different
    schema version or legacy tables (no identifier row) are left untouched.
    Multiple current-version tables are collapsed into one.
    """
    tables = _find_all_log_tables(current_content)

    current_v = [(s, e) for s, e in tables
                 if _extract_table_version(current_content[s:e]) == LOG_SCHEMA_VERSION]

    if not current_v:
        # No current-version table yet — append a new one after existing content
        all_rows, inserted, skipped = _merge_and_sort([], list(new_rows))
        new_table = build_log_table(all_rows)
        before = current_content.strip()
        result = '<br>\n'.join([p for p in [before, new_table] if p])
        return result, inserted, skipped, 0  # 0 = table was freshly created

    # Gather all rows from current-version tables
    all_rows = []
    for s, e in current_v:
        all_rows.extend(parse_log_rows(current_content[s:e]))

    all_rows, inserted, skipped = _merge_and_sort(all_rows, new_rows)
    new_table = build_log_table(all_rows)

    # Rebuild content: replace the first current-version table with the
    # consolidated one; remove any additional current-version tables.
    # Other-version and legacy tables are left exactly where they are.
    result_parts = []
    last_pos = 0
    first_replaced = False
    for s, e in sorted(current_v):
        result_parts.append(current_content[last_pos:s])
        if not first_replaced:
            result_parts.append(new_table)
            first_replaced = True
        # subsequent current-version tables are dropped (merged above)
        last_pos = e
    result_parts.append(current_content[last_pos:])
    return ''.join(result_parts), inserted, skipped, len(current_v)


def bulk_append_to_experiment(api_client, exp_id, new_rows, entity_type='experiments'):
    """Merge new log rows into the entry, sort newest first, skip exact duplicates.

    Consolidates multiple same-version log tables into one.
    Tables of a different schema version are left untouched.
    new_rows: list of (timestamp_str, content_html, initials)
    Returns: (inserted_count, skipped_count)
    """
    if entity_type == 'items':
        names, ids, entries = get_items(api_client)
    else:
        names, ids, entries = get_experiments(api_client)
    current_content = entries[ids.index(exp_id)].body or ''

    new_content, inserted, skipped, _ = _consolidate(current_content, new_rows)

    if entity_type == 'items':
        elabapi_python.ItemsApi(api_client).patch_item(exp_id, body={'body': new_content})
    else:
        elabapi_python.ExperimentsApi(api_client).patch_experiment(exp_id, body={'body': new_content})

    # append inserted rows to session log
    if inserted > 0:
        if 'session_log' not in st.session_state:
            st.session_state['session_log'] = []
        exp_name = st.session_state.get('exp_name', str(exp_id))
        for ts, content_html, inits in new_rows:
            st.session_state['session_log'].append({
                'exp_name':    exp_name,
                'entity_type': entity_type,
                'timestamp':   ts,
                'content':     content_html,   # already HTML from CSV pipeline
                'initials':    inits,
                'n_tables':    None,
                'total_rows':  None,
            })

    return inserted, skipped


def check_log_compatibility(body):
    """Check whether an entry body is compatible with the elab-app log format.

    Returns a dict with:
      status        -- 'no_table' | 'ok' | 'unordered' | 'warnings'
      rows          -- data rows from current-version table(s)
      bad_rows      -- list of (1-based index, row tuple, reason) for invalid rows
      ordered       -- bool, True if timestamps are newest-first
      n_tables      -- number of current-version log tables (>1 → needs consolidation)
      legacy_tables -- number of tables with no identifier row
      other_versions-- list of version strings found in other-version tables
    """
    body = body or ''
    tables = _find_all_log_tables(body)

    if not tables:
        return {'status': 'no_table', 'rows': [], 'bad_rows': [], 'ordered': True,
                'n_tables': 0, 'legacy_tables': 0, 'other_versions': []}

    current_v, legacy, other = [], [], []
    for s, e in tables:
        v = _extract_table_version(body[s:e])
        if v == LOG_SCHEMA_VERSION:
            current_v.append((s, e))
        elif v is None:
            legacy.append((s, e))
        else:
            other.append(v)

    rows = []
    for s, e in current_v:
        rows.extend(parse_log_rows(body[s:e]))

    bad_rows = []
    for i, (ts, content, initials) in enumerate(rows, start=1):
        reasons = []
        try:
            datetime.datetime.fromisoformat(ts)
        except ValueError:
            reasons.append(f"timestamp '{ts}' is not valid ISO 8601")
        if not content.strip():
            reasons.append("log text is empty")
        if not (_SHORT_NAME_RE.match(initials) and len(initials) <= 6):
            reasons.append(f"initials '{initials}' invalid (lowercase, max 6 chars, start with a letter)")
        if reasons:
            bad_rows.append((i, (ts, content, initials), '; '.join(reasons)))

    valid_ts = []
    for ts, _, _ in rows:
        try:
            valid_ts.append(datetime.datetime.fromisoformat(ts))
        except ValueError:
            pass
    ordered = valid_ts == sorted(valid_ts, reverse=True)

    if not current_v:
        status = 'no_table'   # only legacy/other-version tables present
    elif bad_rows:
        status = 'warnings'
    elif len(current_v) > 1 or not ordered:
        status = 'unordered'
    else:
        status = 'ok'

    return {'status': status, 'rows': rows, 'bad_rows': bad_rows,
            'ordered': ordered, 'n_tables': len(current_v),
            'legacy_tables': len(legacy), 'other_versions': list(set(other))}


def get_exp_info(api_client, exp):
    """get summary of an experiment entry
    
    Keyword arguments:
    api_client -- elabapi_python api_client instance
    exp -- experiment entry
     
    Returns:
    info -- summary of the experiment (str)
    """

    info = '''Category: %s
    
    Created by %s on %s
    
    Last modified by %s on %s'''%(exp.category_title, exp.fullname, 
                                  exp.created_at, get_name(api_client, exp.lastchangeby), 
                                  exp.modified_at)
    
    return info

