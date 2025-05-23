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

    now = datetime.datetime.now()
    content = ': '.join([now.strftime("%Y-%m-%d_%H-%M-%S"),content])
    content = content.replace('\n','<br>')
    
    names, ids, exps = get_experiments(api_client)
    ind = ids.index(exp_id)
    current_content = exps[ind].body
    new_content = '<br>'.join([current_content,content])
    experimentsApi = elabapi_python.ExperimentsApi(api_client)
    experimentsApi.patch_experiment(exp_id,body={'body':new_content})
    return True

def append_to_experiment(api_client, exp_id, content):
    
    now = datetime.datetime.now()
    content = content.replace('\n','<br>')

    
    names, ids, exps = get_experiments(api_client)
    ind = ids.index(exp_id)
    current_content = exps[ind].body

    line ='''<tr style="border-width:0px;">
    <td style="border-width:0px;">%s</td>
    <td style="border-width:0px;"> %s</td>
    </tr>'''%(now, content)
    
    if not '<table' in current_content:
    
        line = '\n'.join(['<table style="border-collapse:collapse;width:100%;border-width:0px;" border="1">',line,'</table>']) 
        new_content = new_content = '<br>\n'.join([current_content,line])
    else:
        index = current_content.find('</table>')
        new_content = current_content[:index]+line+'\n'+current_content[index:]
        
    experimentsApi = elabapi_python.ExperimentsApi(api_client)
    experimentsApi.patch_experiment(exp_id,body={'body':new_content})

    return True

def upload_image(api_client, exp_id, path):
    uploadsApi = elabapi_python.UploadsApi(api_client)
    uploadsApi.post_upload('experiments', exp_id, file=path, comment='Uploaded with APIv2')

def get_uploads(api_client, exp_id):
    uploadsApi = elabapi_python.UploadsApi(api_client)
    upls = uploadsApi.read_uploads('experiments',exp_id)
    names = [up.real_name for up in upls]
    return names, upls

def get_image_content(upl, width=141, height=171):
    fn = upl.real_name
    ln = upl.long_name
    s = upl.storage
    src="app/download.php?name=%s&amp;f=%s&amp;storage=%i"%(fn,ln,s)
    cont = '<p><img src="%s" width="%i" height="%i" ></p>'%(src, width, height)
    return cont

def insert_image(api_client, exp_id, name):
    names, upls = get_uploads(api_client, exp_id)
    ind = names.index(name)
    cont = get_image_content(upls[ind])
    append_to_experiment(api_client, exp_id, cont)
    return True

def get_experiments(api_client):
    experimentsApi = elabapi_python.ExperimentsApi(api_client)
    uploadsApi = elabapi_python.UploadsApi(api_client)
    exps = experimentsApi.read_experiments()
    # existing ids 
    names = [exp.title for exp in exps]
    ids = [exp.id for exp in exps]
    return names, ids, exps

def create_experiment(api_client, name, comment='', catid = 0):
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
    uapi = elabapi_python.UsersApi(api_client)
    users = uapi.read_users()
    for u in users:
        if u.fullname == ' '.join([fn,ln]):
            return u.userid
    else:
        print('User %s %s does not exist!'%(fn,ln))
        return None

def get_team_id(api_client, userid):
    uapi = elabapi_python.UsersApi(api_client)
    u = uapi.read_user(userid)
    return u.teams[0].id

def get_categories(api_client, fn, ln):

    team_id = get_team_id(api_client, get_user_id(api_client, fn,ln))
    
    eapi = elabapi_python.ExperimentsCategoriesApi(api_client)
    cats = eapi.read_team_experiments_categories(team_id)
    return [cat.title for cat in cats],[cat.id for cat in cats],[cat.color for cat in cats]

def get_name(api_client, userid):
    uapi = elabapi_python.UsersApi(api_client)
    users = uapi.read_users()
    for u in users:
        if u.userid == userid:
            return u.fullname
    return False

def get_exp_info(api_client, exp):

    info = '''Category: %s
    
    Created by %s on %s
    
    Last modified by %s on %s'''%(exp.category_title, exp.fullname, 
                                  exp.created_at, get_name(api_client, exp.lastchangeby), 
                                  exp.modified_at)
    
    return info
    