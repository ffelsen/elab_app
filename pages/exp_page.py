import streamlit as st
from utils import *
import requests
from elabapi_python import ExperimentsApi
from bs4 import BeautifulSoup
import os
from warnings import filterwarnings
filterwarnings('ignore')

## have to have a team
if not st.session_state['team']:
    st.warning("please login as a member of a team")
    st.stop()

#### Experiment Overview ####
st.title("Experiment Overview")

## get existing Experiments
try:
    names, ids, exps = get_experiments(st.session_state['api_client'])
    if not exps:
        st.info("No Experiments found for this account")
except Exception as e:
    st.error(f"Error while loading Experiments: {e}")
    st.stop()
        
## select Experiment from existing
exp_index = get_index(ids, st.session_state["exp_id"],0)
titles_exps = [f"{name} (ID: {id})" for name, id in zip(names, ids)]
selected_title = st.selectbox( "Select Experiment or create New:", titles_exps, index=exp_index)
exp_index = get_index(titles_exps,selected_title)

## if selected invalid use stored exp_id to get index
if exp_index == -1:
    exp_index = get_index(st.session_state["exp_id"])

## set selected experiment if exists
if exp_index!=-1:
    st.session_state["exp_id"] = ids[exp_index]
    st.session_state["exp_name"] = names[exp_index]
    selected_exp = exps[exp_index]

## or create new experiment
cat = None
cats, cat_ids, cat_colors = get_categories(st.session_state["api_client"], st.session_state["team_id"])
col_exp_old, col_exp_cat, col_exp_new = st.columns([4,1,1])
with col_exp_old:
    new_title = st.text_input( "create new", label_visibility="collapsed", width="stretch", placeholder="Name of new Experiment")
with col_exp_cat:
    cat = st.selectbox('Category', ["Not set"] + cats, index=0, label_visibility="collapsed")
with col_exp_new:
    if st.button("➕ Create"):
        if new_title.strip() != "":
            catid = None if cat == "Not set" else ids[cats.index(cat)]
            create_experiment(st.session_state["api_client"], new_title, "Description...", catid)
            st.rerun()
st.markdown("---")

#### get experiment ####
exp_client = ExperimentsApi(st.session_state["api_client"])
experiment = exp_client.get_experiment(st.session_state["exp_id"])
if experiment.body!=None:
    body_soup = BeautifulSoup(experiment.body, 'html.parser')
else:
    body_soup = BeautifulSoup("", 'html.parser')

## update experiment with path
def update_exp_path(body_soup, path_str):
    ## find the resource section in html or create it before table
    resc_div = body_soup.find('div', class_='resc')
    if not resc_div:
        resc_div = body_soup.new_tag("div", attrs={'class': 'resc'})
        resc_h = body_soup.new_tag("h5")
        strong = body_soup.new_tag("strong")
        strong.string = "Resources:"
        resc_h.append(strong)
        resc_div.append(resc_h)
        resc_ul = body_soup.new_tag("ul")
        resc_div.append(resc_ul)
        first_table = body_soup.find('table')
        if first_table:
            first_table.insert_before(resc_div)
        else:
            body_soup.append(resc_div)

    ## find list <ul> in resources or create it
    resc_ul = resc_div.find('ul')
    if not resc_ul:
        ## make sure a header exists before the list
        resc_h = resc_div.find(['h3', 'h4', 'h5'])
        if not resc_h:
            resc_h = body_soup.new_tag("h5")
            strong = body_soup.new_tag("strong")
            strong.string = "Resources:"
            resc_h.append(strong)
            resc_div.insert(0, resc_h)
        resc_ul = body_soup.new_tag("ul")
        resc_h.insert_after(resc_ul)

    ## create linked path list element <li>
    new_li = body_soup.new_tag('li')
    strong_tag = body_soup.new_tag('strong')
    strong_tag.string = 'Linked Path'
    div_tag = body_soup.new_tag('div', attrs={'class': 'path', 'style': 'display:inline;'})
    div_tag.string = path_str
    new_li.append(strong_tag)
    new_li.append(': ')
    new_li.append(div_tag)

    # replace existing linked path and replace or append it to <ul> list
    existing_div = resc_ul.find('div', class_='path')
    if existing_div:
        existing_li = existing_div.find_parent('li')
        if existing_li:
            existing_li.replace_with(new_li)
    else:
        resc_ul.append(new_li)
        
    ## patch experiment body with new html
    response = exp_client.patch_experiment(st.session_state["exp_id"], body={ 'body': str(body_soup) })
        
## input new path
col_path, col_submitpath = st.columns([8,2])
with col_path:
    st.session_state.file_path = st.text_input("Path Linked To Experiment:", value=st.session_state.file_path, placeholder="e.g., C:/Users/.../Data/MyExperiment/")
with col_submitpath:
    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    if st.button("Update",key="sub_path"):
        if st.session_state.file_path!="":
            path = os.path.expanduser(st.session_state.file_path)
            os.makedirs(path, exist_ok=True)
            update_exp_path(body_soup, st.session_state.file_path)
            if not os.path.exists(path):
                st.warning(f"Path may not exist: '{path}'")
            st.rerun()

## title
st.subheader( experiment.title )

## body
st.markdown("---")
st.markdown(experiment.body, unsafe_allow_html=True)

st.success(f"Ausgewählte Experiment-ID: {st.session_state['exp_id']} – diese ID ist nun auf allen Seiten verfügbar")


