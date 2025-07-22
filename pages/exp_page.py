import streamlit as st
from utils import *
import requests
from elabapi_python import ExperimentsApi
from bs4 import BeautifulSoup
from warnings import filterwarnings
filterwarnings('ignore')

## have to have a team
if not st.session_state['team']:
    st.warning("please login as a member of a team")
    st.stop()

## get smallest positive int not in array
def smallest_available(arr):
    n = 1
    while n in arr:
        n += 1
    return n

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

## get index of current experiment
idx = 0
for i in range(0,len(ids)):
    if ids[i] == st.session_state["exp_id"]:
        idx = i
        break
## select Experiment from existing
exp_titles = [f"{name} (ID: {id})" for name, id in zip(names, ids)]
new_id = -1
selected_title = st.selectbox( "Select Experiment or create New:", exp_titles, index=idx)

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
        new_id = smallest_available(ids)
        if new_title.strip() != "":
            catid = None if cat == "Not set" else ids[cats.index(cat)]
            selected_title = f"{new_title} (ID: {new_id})"
            create_experiment(st.session_state["api_client"], new_title, "Description...", catid)
            st.rerun()

st.session_state["exp_id"] = int(selected_title.split("(ID: ")[1].rstrip(")"))
exp_index = ids.index(st.session_state["exp_id"])
selected_exp= exps[exp_index]
st.markdown("---")

#### get experiment ####
exp_client = ExperimentsApi(st.session_state["api_client"])
experiment = exp_client.get_experiment(st.session_state["exp_id"])
if experiment.body!=None:
    body_soup = BeautifulSoup(experiment.body, 'html.parser')
else:
    body_soup = BeautifulSoup("", 'html.parser')

## title
st.subheader( experiment.title )

## resources
# resc_html = "<big><b>Resources</b></big><ul>"
# for i, items_link in enumerate(experiment.items_links):
    # resc_html += ( f"<li>Sample {i+1}: {items_link.title}</li>" )
# if (experiment.items_links==None):
    # resc_html += "..."

# ## get positions
# resc_ul = body_soup.find('ul', class_='resc')
# if resc_ul!=None:
    # positions = [a.get_text() for a in resc_ul.find_all('a', class_='pos')]

# resc_html += "</ul>"
# st.markdown(resc_html, unsafe_allow_html=True)

## body
st.markdown("---")
st.markdown(experiment.body, unsafe_allow_html=True)

st.success(f"Ausgewählte Experiment-ID: {st.session_state['exp_id']} – diese ID ist nun auf allen Seiten verfügbar")


