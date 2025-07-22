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
import os
import requests
from elabapi_python import UploadsApi

def get_linked_resources(api_client, exp_id):
    api_key  = api_client.configuration.api_key['api_key']
    base_url = api_client.configuration.host.rstrip('/')
    url      = f"{base_url}/experiments/{exp_id}/items_links"
    headers  = {"Authorization": api_key}

    response = requests.get(url, headers=headers, verify=False)
    if response.status_code != 200:
        raise Exception(f"API error {response.status_code}: {response.text}")

    linked_items = response.json()
    resources = []
    for item in linked_items:
        resources.append({
            'id':         item.get('itemid'),
            'title':      item.get('title'),
            'category':   item.get('category_title'),
            'created_at': item.get('created_at'),
            # <-- hier:
            'body':       item.get('body') or ""
        })

    return resources

def get_resources(api_client, team_id):
    headers = {"Authorization": f"Bearer {api_client.configuration.access_token}"}
    url = f"{api_client.configuration.host}/api/v1/team/{team_id}/resources"

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    
    # Struktur: {"id": ..., "name": ..., "category": ...}
    return data

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

def append_to_experiment(api_client, exp_id, content):
    """Append a time stamped comment to an ElabFTW entry
    in a tabular format

    Keyword arguments:
    api_client -- elabapi_python api_client instance
    exp_id -- id of the elab entry of the experiment
    content -- content to add to the line (str)
    """
    
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    content = content.replace('\n','<br>')
 
    # get current content of the experiment
    names, ids, exps = get_experiments(api_client)
    ind = ids.index(exp_id)
    current_content = exps[ind].body

    # add new content
    line ='''<tr style="border-width:0px;">
    <td style="border-width:0px;">%s</td>
    <td style="border-width:0px;"> %s</td>
    </tr>'''%(now, content)
    
    if not '<table' in current_content: # create a new table in the entry if there is none
    
        line = '\n'.join(['<table style="border-collapse:collapse;width:100%;border-width:0px;" border="1">',line,'</table>']) 
        new_content = new_content = '<br>\n'.join([current_content,line])
    else:
        index = current_content.find('</table>')
        new_content = current_content[:index]+line+'\n'+current_content[index:]
        
    # initialize experiments api
    experimentsApi = elabapi_python.ExperimentsApi(api_client)
    # upload new content
    experimentsApi.patch_experiment(exp_id,body={'body':new_content})
    return True

def upload_image(api_client, exp_id, path):
    """Upload image to experiment and return clickable link
    
    Args:
        api_client: elabapi_python api_client instance
        exp_id: ID of the experiment entry
        path: Path to the image file
    
    Returns:
        bool: True if successful
    """
    try:
        uploadsApi = elabapi_python.UploadsApi(api_client)
        img = Image.open(path)
        size = img.size
        uploadsApi.post_upload('experiments', exp_id, file=path, comment='%i:%i'%size)
        return True
    except Exception as e:
        print(f"Error uploading image: {e}")
        return False

def get_uploads(api_client, exp_id):
    """read all uploads connected to an experiment

    Keyword arguments:
    api_client -- elabapi_python api_client instance
    exp_id -- id of the elab entry of the experiment

    Returns:
    names -- names of the uploads
    upls -- list of full upload entries
    """
    uploadsApi = elabapi_python.UploadsApi(api_client)
    upls = uploadsApi.read_uploads('experiments',exp_id)
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

def insert_image(api_client, exp_id, filename):
    """Insert clickable image link with filename into experiment"""
    try:
        # Uploads zum Experiment holen
        _, uploads = get_uploads(api_client, exp_id)

        # Upload mit übereinstimmendem Dateinamen finden
        match = next((u for u in uploads if u.real_name == filename), None)
        if not match:
            print(f"Image {filename} not found among uploads.")
            return False

        # Bild-Link korrekt erzeugen
        src = f"app/download.php?name={match.real_name}&amp;f={match.long_name}&amp;storage={match.storage}"

        # Sichtbaren Button mit Dateinamen anzeigen
        image_link = f"""
        <div style="margin:10px 0;">
            <a href="{src}" target="_blank" style="text-decoration:none;">
                <button style="
                    background-color:#4a6ea9;
                    color:white;
                    padding:8px 15px;
                    border:none;
                    border-radius:4px;
                    cursor:pointer;
                    font-size:14px;">
                    📷 View Image: {match.real_name}
                </button>
            </a>
        </div>
        """

        # In ElabFTW einfügen
        append_to_experiment(api_client, exp_id, image_link)
        return True

    except Exception as e:
        print(f"Error inserting image link: {e}")
        return False

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

def create_experiment(api_client, name, comment='', catid=None):
    """
    Create a new experiment entry in eLabFTW

    Keyword arguments:
    api_client -- elabapi_python api_client instance
    name -- name of the new experiment 
    comment -- comment to add in the first line of the new entry
    catid -- id of the experiment category (None = not set)
    """
    experimentsApi = elabapi_python.ExperimentsApi(api_client)
    
    # Create empty experiment
    experimentsApi.post_experiment()
    
    # Get latest "Untitled" experiment
    names, ids, exps = get_experiments(api_client)
    exp_id = ids[names.index('Untitled')]
    
    # Set title
    experimentsApi.patch_experiment(exp_id, body={'title': name})
    
    # Set optional comment
    if comment:
        experimentsApi.patch_experiment(exp_id, body={'body': comment})
    
    # Set category only if specified
    if catid is not None:
        experimentsApi.patch_experiment(exp_id, body={'category': catid})

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

def link_resource_to_exp(api_client, exp_id, res_id):
    api_client.call_api(
        f'/api/v1/experiment/{exp_id}/resource/{res_id}',
        'POST',
        auth_settings=['apiKeyAuth'],
        response_type=None
    )
