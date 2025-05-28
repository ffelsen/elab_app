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

def append_to_experiment(api_client, exp_id, content):
    """Append a time stamped comment to an ElabFTW entry
    in a tabular format

    Keyword arguments:
    api_client -- elabapi_python api_client instance
    exp_id -- id of the elab entry of the experiment
    content -- content to add to the line (str)
    """
    
    now = datetime.datetime.now()
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
    """upload image to an experiment entry

    Keyword arguments:
    api_client -- elabapi_python api_client instance
    exp_id -- id of the elab entry of the experiment
    path -- path of the image file to upload (str)
    """
    uploadsApi = elabapi_python.UploadsApi(api_client)
    uploadsApi.post_upload('experiments', exp_id, file=path, comment='Uploaded with APIv2')
    return True

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

def get_image_content(upl, width=141, height=171):
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
    src="app/download.php?name=%s&amp;f=%s&amp;storage=%i"%(fn,ln,s)
    cont = '<p><img src="%s" width="%i" height="%i" ></p>'%(src, width, height)
    return cont

def insert_image(api_client, exp_id, name):
    """insert image into experiment entry

    Keyword arguments:
    api_client -- elabapi_python api_client instance
    exp_id -- id of the elab entry of the experiment
    name -- name of the uploaded image
    """
    names, upls = get_uploads(api_client, exp_id)
    ind = names.index(name)
    cont = get_image_content(upls[ind])
    append_to_experiment(api_client, exp_id, cont)
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

def get_team_id(api_client, userid):
    """get the id of team the current user 
    is assigned to 
    
    Keyword arguments:
    api_client -- elabapi_python api_client instance
    userid -- id of the user
     
    Returns:
    u.teams[0].id -- id of the team 
    """
    uapi = elabapi_python.UsersApi(api_client)
    u = uapi.read_user(userid)
    return u.teams[0].id # does currently not support multi-team-assignments!

def get_categories(api_client, fn, ln):
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

    team_id = get_team_id(api_client, get_user_id(api_client, fn,ln))
    
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
    
