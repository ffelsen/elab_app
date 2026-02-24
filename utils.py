import streamlit as st
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

def append_to_experiment(api_client, exp_id, content, custom_timestamp=None, entity_type='experiments'):
    """Append a time stamped comment to an ElabFTW entry
    in a tabular format

    Keyword arguments:
    api_client -- elabapi_python api_client instance
    exp_id -- id of the elab entry of the experiment or item
    content -- content to add to the line (str)
    custom_timestamp -- optional custom timestamp string (if None, uses current time)
    entity_type -- 'experiments' or 'items' (default: 'experiments')
    """

    # Use custom timestamp if provided, otherwise use current time
    if custom_timestamp is not None:
        timestamp = custom_timestamp
    else:
        now = datetime.datetime.now()
        timestamp = now

    content = md.markdown(content)

    # get current content of the entry
    if entity_type == 'items':
        names, ids, entries = get_items(api_client)
    else:
        names, ids, entries = get_experiments(api_client)
    ind = ids.index(exp_id)
    current_content = entries[ind].body

    # add new content
    line ='''<tr style="border-width:0px;">
    <td style="border-width:0px;">%s</td>
    <td style="border-width:0px;"> %s</td>
    </tr>'''%(timestamp, content)

    if not '<table' in current_content: # create a new table in the entry if there is none

        line = '\n'.join(['<table style="border-collapse:collapse;width:100%;border-width:0px;" border="1">',line,'</table>'])
        new_content = '<br>\n'.join([current_content,line])
    else:
        index = current_content.find('</table>')
        new_content = current_content[:index]+line+'\n'+current_content[index:]

    # patch the entry
    if entity_type == 'items':
        itemsApi = elabapi_python.ItemsApi(api_client)
        itemsApi.patch_item(exp_id, body={'body': new_content})
    else:
        experimentsApi = elabapi_python.ExperimentsApi(api_client)
        experimentsApi.patch_experiment(exp_id, body={'body': new_content})
    return True

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

