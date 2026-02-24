import streamlit as st
import numpy as np
import pandas as pd
from datetime import date
import calendar
import elabapi_python 
from elabapi_python.rest import ApiException
from warnings import filterwarnings
import datetime
import os
from PIL import Image
from uuid import uuid4
from utils import *

filterwarnings('ignore')

from streamlit_drawable_canvas import st_canvas

st.title ("eLabFTW Log")

st.header('Draw a sketch and add it to the entry')

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

if st.button('Upload drawing'):
    iid = uuid4()
    im = Image.fromarray(canvas_result.image_data)

    # Create temp directory if it doesn't exist
    temp_dir = './temp'
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    file_name = './temp/%s.png' % iid
    im.save(file_name, "PNG")
    entity_type = st.session_state.get('entity_type', 'experiments')
    upload_image(st.session_state.api_client, st.session_state.exp_id, file_name, entity_type=entity_type)
    insert_image(st.session_state.api_client, st.session_state.exp_id, file_name.split('/')[-1], entity_type=entity_type)
#if canvas_result.json_data is not None:
#    objects = pd.json_normalize(canvas_result.json_data["objects"])
#    for col in objects.select_dtypes(include=["object"]).columns:
#        objects[col] = objects[col].astype("str")
#    st.dataframe(objects)
