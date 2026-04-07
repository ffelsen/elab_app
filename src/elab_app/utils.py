import re
import streamlit as st
from version import LOG_SCHEMA_VERSION, LOG_SCHEMA_APP, LOG_SCHEMA_URL
import elabapi_python
import datetime
from PIL import Image
import markdown as md

def _attr(obj, key):
    """Read *key* from either an object (attribute) or a dict — handles both
    elabapi_python >=5.5 (returns dicts) and <5.3 (returns model objects)."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)

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
    experimentsApi.patch_experiment(body={'body': new_content}, id=exp_id)
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

    new_row = (timestamp, content_html, initials, LOG_SCHEMA_VERSION)
    new_content, inserted, skipped, n_tables = _consolidate(current_content, [new_row])

    # patch the entry
    if entity_type == 'items':
        elabapi_python.ItemsApi(api_client).patch_item(body={'body': new_content}, id=exp_id)
    else:
        elabapi_python.ExperimentsApi(api_client).patch_experiment(body={'body': new_content}, id=exp_id)

    # mirror any elabFTW internal links in the log text as proper database links
    _create_links_from_html(api_client, entity_type, exp_id, content_html)

    # count total rows in the updated table for the session log
    all_tables = _find_all_log_tables(new_content)
    total_rows = sum(len(parse_log_rows(new_content[s:e])) for s, e in all_tables)

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
    if not width or not height:
        width, height = [int(i) for i in upl.comment.split(':')]
    
    src="app/download.php?name=%s&amp;f=%s&amp;storage=%i"%(fn,ln,s)
    cont = '<p><img src="%s" width="%i" height="%i" ></p>'%(src, width, height)
    return cont

def insert_image(api_client, exp_id, name, entity_type='experiments', initials=''):
    """insert image into experiment or item entry

    Keyword arguments:
    api_client -- elabapi_python api_client instance
    exp_id -- id of the elab entry of the experiment or item
    name -- name of the uploaded image
    entity_type -- 'experiments' or 'items' (default: 'experiments')
    initials -- user initials to record in the log table (default: '')
    """
    names, upls = get_uploads(api_client, exp_id, entity_type=entity_type)
    ind = names.index(name)
    cont = get_image_content(upls[ind])
    append_to_experiment(api_client, exp_id, cont, entity_type=entity_type, initials=initials)
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
    itemsApi.patch_item(body={'title': name}, id=item_id)
    if comment != '':
        itemsApi.patch_item(body={'body': comment}, id=item_id)
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
    experimentsApi.patch_experiment(body={'title': name}, id=exp_id)
    if comment != '':
        experimentsApi.patch_experiment(body={'body': comment}, id=exp_id)
    experimentsApi.patch_experiment(body={'category': catid}, id=exp_id)

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
        if _attr(u, 'fullname') == ' '.join([fn, ln]):
            return _attr(u, 'userid')
    print('User %s %s does not exist!' % (fn, ln))
    return None

def get_teams(api_client, userid):
    """get the ids and names of teams the current user
    is assigned to

    Keyword arguments:
    api_client -- elabapi_python api_client instance
    userid -- id of the user

    Returns:
    ids   -- list of team ids
    names -- list of team names
    """
    tapi = elabapi_python.TeamsApi(api_client)
    teams = tapi.read_teams() or []
    return [_attr(t, 'id') for t in teams], [_attr(t, 'name') for t in teams]

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
        if _attr(u, 'userid') == userid:
            return _attr(u, 'fullname')
    return False

# ── Log-table helpers ─────────────────────────────────────────────────────────
# Detection is signature-based: we look for any <table> that contains the
# distinctive header text "ISO time (ISO 8601)".  elabFTW strips id/class
# attributes on save, so ID-based detection is not reliable.
#
# Each table written by the app starts with an identifier row:
#   elab_app | <repo URL> | (empty) | (empty)
# This row survives elabFTW's sanitisation (text content is preserved).
# Per-row versioning: each data row carries its own app_version in the 4th column.

_LOG_SIGNATURE = 'ISO time'   # present in all elab-app table headers; kept short to survive formatting changes
_ROW_RE = re.compile(r'<tr[^>]*>(.*?)</tr>', re.DOTALL | re.IGNORECASE)
_TD_RE  = re.compile(r'<td[^>]*>(.*?)</td>', re.DOTALL | re.IGNORECASE)
_SHORT_NAME_RE = re.compile(r'^[a-z][a-z0-9_]*$')
# Detect elabFTW internal hrefs so we can mirror them as proper database links
_ITEM_LINK_RE  = re.compile(r'database\.php\?mode=view&(?:amp;)?id=(\d+)', re.IGNORECASE)
_EXP_LINK_RE   = re.compile(r'experiments\.php\?mode=view&(?:amp;)?id=(\d+)', re.IGNORECASE)


def _create_links_from_html(api_client, entity_type, entity_id, content_html):
    """Parse content_html for elabFTW internal resource/experiment links and create
    them as proper database-level links on the entry.

    elabFTW's own editor does this automatically; this mirrors that behaviour for
    links inserted through elab_app.  Errors are silently ignored (e.g. the link
    already exists, or the referenced entry is not accessible).

    Detects:
      database.php?mode=view&id=XXXX    → items_links  (resources)
      experiments.php?mode=view&id=XXXX → experiments_links
    """
    item_ids = {int(m) for m in _ITEM_LINK_RE.findall(content_html)}
    exp_ids  = {int(m) for m in _EXP_LINK_RE.findall(content_html)}

    if item_ids:
        link_api = elabapi_python.LinksToItemsApi(api_client)
        for item_id in item_ids:
            try:
                link_api.post_entity_items_links(entity_type, entity_id, item_id)
            except Exception:
                pass

    if exp_ids:
        link_api = elabapi_python.LinksToExperimentsApi(api_client)
        for linked_exp_id in exp_ids:
            try:
                link_api.post_entity_experiments_links(entity_type, entity_id, linked_exp_id)
            except Exception:
                pass


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


def parse_log_rows(html):
    """Extract data rows from a log table HTML.

    Skips the identifier row and header rows (which have <th> cells, not <td>).
    Returns a list of (timestamp_str, content_html, initials, app_version) tuples.
    v2.x tables have 3 columns; their rows are backfilled with '2.x' as app_version.
    """
    rows = []
    for row_match in _ROW_RE.finditer(html or ''):
        tds = _TD_RE.findall(row_match.group(1))
        if len(tds) == 4 and tds[0].strip() != LOG_SCHEMA_APP:
            rows.append((tds[0].strip(), tds[1].strip(), tds[2].strip(), tds[3].strip()))
        elif len(tds) == 3 and tds[0].strip() != LOG_SCHEMA_APP:
            rows.append((tds[0].strip(), tds[1].strip(), tds[2].strip(), '2.x'))
    return rows


def build_log_table(rows):
    """Build the elab-app log table HTML from a list of rows (newest first).

    rows: list of (timestamp_str, content_html, initials, app_version)
    The first row is the identifier row (2 content cells + 2 empty); the second is the column header.
    Note: elabFTW strips custom attributes on save, so we use plain tags.
    Versioning is per-row (app_version column), not per-table.
    """
    id_row = '<tr><td>%s</td><td>%s</td><td></td><td></td></tr>' % (
        LOG_SCHEMA_APP, LOG_SCHEMA_URL)
    header = '<tr><th>ISO time<br>(ISO 8601)</th><th>Log<br>(newest to oldest)</th><th>Initials</th><th>App<br>version</th></tr>'
    tr_blocks = [id_row, header]
    for ts, content, initials, app_ver in rows:
        tr_blocks.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (ts, content, initials, app_ver))
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
    """Merge new_rows into existing log tables, sort newest first, return
    (new_full_content, inserted, skipped, n_tables).

    All log tables found are merged into one consolidated table regardless of
    which app version wrote them. Per-row versioning (app_version column) tracks
    provenance; no per-table version gating is needed.
    """
    tables = _find_all_log_tables(current_content)

    if not tables:
        # No log table yet — append a new one after existing content
        all_rows, inserted, skipped = _merge_and_sort([], list(new_rows))
        new_table = build_log_table(all_rows)
        before = current_content.strip()
        result = '<br>\n'.join([p for p in [before, new_table] if p])
        return result, inserted, skipped, 0

    # Gather all rows from all log tables
    all_rows = []
    for s, e in tables:
        all_rows.extend(parse_log_rows(current_content[s:e]))

    all_rows, inserted, skipped = _merge_and_sort(all_rows, new_rows)
    new_table = build_log_table(all_rows)

    # Rebuild content: replace the first log table with the consolidated one;
    # remove any additional log tables.
    result_parts = []
    last_pos = 0
    first_replaced = False
    for s, e in sorted(tables):
        result_parts.append(current_content[last_pos:s])
        if not first_replaced:
            result_parts.append(new_table)
            first_replaced = True
        last_pos = e
    result_parts.append(current_content[last_pos:])
    return ''.join(result_parts), inserted, skipped, len(tables)


def bulk_append_to_experiment(api_client, exp_id, new_rows, entity_type='experiments'):
    """Merge new log rows into the entry, sort newest first, skip exact duplicates.

    Consolidates all log tables into one.
    new_rows: list of (timestamp_str, content_html, initials, app_version)
    Returns: (inserted_count, skipped_count)
    """
    if entity_type == 'items':
        names, ids, entries = get_items(api_client)
    else:
        names, ids, entries = get_experiments(api_client)
    current_content = entries[ids.index(exp_id)].body or ''

    new_content, inserted, skipped, _ = _consolidate(current_content, new_rows)

    if entity_type == 'items':
        elabapi_python.ItemsApi(api_client).patch_item(body={'body': new_content}, id=exp_id)
    else:
        elabapi_python.ExperimentsApi(api_client).patch_experiment(body={'body': new_content}, id=exp_id)

    # append inserted rows to session log
    if inserted > 0:
        if 'session_log' not in st.session_state:
            st.session_state['session_log'] = []
        exp_name = st.session_state.get('exp_name', str(exp_id))
        for ts, content_html, inits, *_ in new_rows:
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
      status   -- 'no_table' | 'ok' | 'unordered' | 'warnings'
      rows     -- data rows from all log tables
      bad_rows -- list of (1-based index, row tuple, reason) for invalid rows
      ordered  -- bool, True if timestamps are newest-first
      n_tables -- number of log tables found (>1 → needs consolidation)
    """
    body = body or ''
    tables = _find_all_log_tables(body)

    if not tables:
        return {'status': 'no_table', 'rows': [], 'bad_rows': [], 'ordered': True,
                'n_tables': 0}

    rows = []
    for s, e in tables:
        rows.extend(parse_log_rows(body[s:e]))

    bad_rows = []
    for i, (ts, content, initials, app_ver) in enumerate(rows, start=1):
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
            bad_rows.append((i, (ts, content, initials, app_ver), '; '.join(reasons)))

    valid_ts = []
    for ts, _, _, _ in rows:
        try:
            valid_ts.append(datetime.datetime.fromisoformat(ts))
        except ValueError:
            pass
    ordered = valid_ts == sorted(valid_ts, reverse=True)

    if bad_rows:
        status = 'warnings'
    elif len(tables) > 1 or not ordered:
        status = 'unordered'
    else:
        status = 'ok'

    return {'status': status, 'rows': rows, 'bad_rows': bad_rows,
            'ordered': ordered, 'n_tables': len(tables)}


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

