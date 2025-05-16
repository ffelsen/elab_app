import streamlit as st
import numpy as np
import pandas as pd
from datetime import date
import calendar
import elabapi_python 
from elabapi_python.rest import ApiException
from warnings import filterwarnings
import datetime
filterwarnings('ignore')
with open('digi.key','r') as f:
    key = f.readline().strip()

configuration = elabapi_python.Configuration()
configuration.api_key['api_key'] = key
configuration.api_key_prefix['api_key'] = 'Authorization'
configuration.host = 'https://elabftw-qa-2024.zit.ph.tum.de/api/v2'
configuration.debug = False
configuration.verify_ssl = False
api_client = elabapi_python.ApiClient(configuration)
api_client.set_default_header(header_name='Authorization', header_value=key)

def get_experiments(api_client):
    experimentsApi = elabapi_python.ExperimentsApi(api_client)
    uploadsApi = elabapi_python.UploadsApi(api_client)
    exps = experimentsApi.read_experiments()
    # existing ids 
    names = [exp.title for exp in exps]
    ids = [exp.id for exp in exps]
    return names, ids, exps

def append_to_experiment(api_client, exp_id, content):

    now = datetime.datetime.now()
    content = ': '.join([now.strftime("%Y-%m-%d_%H-%M-%S"),content])
    
    names, ids, exps = get_experiments(api_client)
    ind = ids.index(exp_id)
    current_content = exps[ind].body
    new_content = '<br>'.join([current_content,content])
    experimentsApi = elabapi_python.ExperimentsApi(api_client)
    experimentsApi.patch_experiment(exp_id,body={'body':new_content})
    return True

def clear_text(): 
  st.session_state["text"] = '' 

st.title ("eLabFTW Log")

st.header('Select a notebook entry')
names, ids, exps = get_experiments(api_client)


exp_name = st.selectbox('Experiment title:', names, index=0)
exp_id = ids[names.index(exp_name)]
st.link_button('Open eLabFTW entry', url ='https://elabftw-qa-2024.zit.ph.tum.de/experiments.php?mode=view&id=%i'%exp_id)

st.header('Add a comment to the notebook')


content = st.text_input('Comment:', key='text')

st.button('Clear text', on_click=clear_text)
if st.button('Submit'):
    append_to_experiment(api_client, exp_id, content)
    st.write("Added comment to %s"%exp_name, )
    
from streamlit_drawable_canvas import st_canvas
drawing_mode = st.sidebar.selectbox(
    "Drawing tool:",
    ("freedraw", "line", "rect", "circle", "transform", "polygon", "point"),
)
stroke_width = st.sidebar.slider("Stroke width: ", 1, 25, 3)
if drawing_mode == "point":
    point_display_radius = st.sidebar.slider("Point display radius: ", 1, 25, 3)
stroke_color = st.sidebar.color_picker("Stroke color hex: ")
bg_color = st.sidebar.color_picker("Background color hex: ", "#eee")
bg_image = st.sidebar.file_uploader("Background image:", type=["png", "jpg"])
realtime_update = st.sidebar.checkbox("Update in realtime", True)

# Create a canvas component
canvas_result = st_canvas(
    fill_color="rgba(255, 165, 0, 0.3)",  # Fixed fill color with some opacity
    stroke_width=stroke_width,
    stroke_color=stroke_color,
    background_color=bg_color,
    background_image=Image.open(bg_image) if bg_image else None,
    update_streamlit=realtime_update,
    height=150,
    drawing_mode=drawing_mode,
    point_display_radius=point_display_radius if drawing_mode == "point" else 0,
    display_toolbar=st.sidebar.checkbox("Display toolbar", True),
    key="full_app",
)

# Do something interesting with the image data and paths
if canvas_result.image_data is not None:
    st.image(canvas_result.image_data)
if canvas_result.json_data is not None:
    objects = pd.json_normalize(canvas_result.json_data["objects"])
    for col in objects.select_dtypes(include=["object"]).columns:
        objects[col] = objects[col].astype("str")
    st.dataframe(objects)
