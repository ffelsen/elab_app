import streamlit as st
import os
from elabapi_python import ItemsApi, ExperimentsApi
from bs4 import BeautifulSoup
from inputparsing import *
from utils import get_index

### Define Position ####
st.title("Define Position")

## Make sure an Experiment is selected
if not st.session_state["exp_id"]:
    st.warning("please select an Experiment")
    st.stop()
## Make sure a Sample is selected
if (st.session_state["sample_id"]==None):
    st.warning("please select a Sample")
    st.stop()

## setp data
step_data = {
    "positions": [],
}

#### update function ####
def update_exp_positions(exp_client, body_soup):
    ## remove Positions from html 
    resc_div = body_soup.find('div', class_='resc')
    resc_ul = resc_div.find('ul')
    if not resc_ul:
        resc_h = body_soup.find(['h3','h4','h5'])
        if resc_h:
            resc_ul = body_soup.new_tag("ul")
            resc_h.insert_after(resc_ul)
    last_resc_li = None
    lis = resc_ul.find_all('li', recursive=False) if resc_ul else []
    for li in lis:
        if li.find('div', class_='smpl'):
            last_smpl_li = li
        elif li.find('div', class_='pos'):
            li.decompose()

    ## inset new Positions
    for i, pos in enumerate(step_data["positions"]):
        txt = []
        for key in ['x','y','z']:
            if key in pos['pos']:
                txt.append(f"{key} = {pos['pos'][key]} mm")
            elif ('angle' in pos['pos'])and(pos['pos']['angle']!=0):
                txt.append(f"angle = {pos['pos']['angle']} °")
            else:
                txt.append(f"{key} = 0")
        txt = ", ".join(txt)
        new_li = body_soup.new_tag('li')
        new_b = body_soup.new_tag('strong')
        new_b.string = f"Position {i+1}"
        pos_div = body_soup.new_tag('div', **{'class': 'pos', 'style': 'display: inline;'})
        pos_div.string = txt
        new_li.append(new_b)
        new_li.append(": ")
        new_li.append(pos_div)
        if last_resc_li:
            last_resc_li.insert_after(new_li)
            last_resc_li = new_li
        else:
            resc_ul.append(new_li)
            last_resc_li = new_li
    ## patch experiment with new body
    response = exp_client.patch_experiment(st.session_state["exp_id"], body={ 'body': str(body_soup) })

#### Select and Edit Positions ####
## get experiment
exp_client = ExperimentsApi(st.session_state["api_client"])
experiment = exp_client.get_experiment(st.session_state["exp_id"])

body_soup = BeautifulSoup(experiment.body or "", 'html.parser')
if body_soup.find('div', class_='resc'):
    try:
        count = 0
        for div in body_soup.find_all('div', class_='pos'):
            txt = div.get_text(strip=True).replace("mm","").replace("°","").replace(" ","")
            txt = txt.split(',')
            pos = {}
            for param in txt:
                if '=' in param:
                    key, value = param.split("=", 1)
                    try:
                        value = round(float(value),12)
                    except ValueError:
                        value = 0.0
                    pos[key] = value
            if any(k in pos for k in ['x','y','z']):
                step_data['positions'].append( { 'name':f"Position {count+1}", 'pos':pos} )
                count += 1
    except AttributeError as e:
        st.info(f"possibly missing Position Information?")
else:
    ## if no resource section create one 
    html_new = (
        "<div class='resc'>"
        "<hr>"
        "<h5><strong>Resources:<strong></h5>"
        "<ul>"
        "</ul>"
        "<hr>"
        "</div>")
    new_soup = BeautifulSoup(html_new or "", 'html.parser')
    dscrpt_p = body_soup.find('p', class_='dscrpt')
    if dscrpt_p:
        dscrpt_p.insert_after( new_soup )
    else:
        if body_soup.contents:
            body_soup.contents[0].insert_before( new_soup )
        else:
            body_soup.append( new_soup )
print("POS: ",step_data['positions'])

## select position to edit
options_positions = [ pos['name'] for pos in step_data['positions'] ]
col_old_pos, col_old_del, col_new_pos = st.columns([9,2,2])
pos_old_idx = -1
with col_old_pos:
    pos_old_idx = get_index(options_positions, st.selectbox("Select linked Position to Edit:", options_positions))
with col_old_del:
    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    if st.button("❌ Delete", key="butt_delete"):
        if pos_old_idx !=-1:
            del step_data['positions'][pos_old_idx]
            update_exp_positions(exp_client, body_soup)
            st.rerun()
with col_new_pos:
    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    if st.button("➕ Create", key="butt_create"):
        idx = len(step_data['positions'])
        step_data['positions'].append( { 'name':f"Position {idx}", 'pos':{ 'x':0.0, 'y':0.0, 'z':0.0, 'angle':None }} )
        update_exp_positions(exp_client, body_soup)
        st.rerun()
        
if pos_old_idx!=-1:
    pos_inp_data = step_data["positions"][pos_old_idx]['pos']
else:
    pos_inp_data = { 'x':0.0, 'y':0.0, 'z':0.0, 'angle':0.0 }

col_x, col_y, col_z = st.columns(3)
with col_x:
    pos_inp_data['x'] = st.number_input("Enter x value:", value=float(pos_inp_data['x']), format="%.2f")
with col_y:
    pos_inp_data['y'] = st.number_input("Enter y value:", value=float(pos_inp_data['y']), format="%.2f")
with col_z:
    pos_inp_data['z'] = st.number_input("Enter z value:", value=float(pos_inp_data['z']), format="%.2f")

#### Update Experiments Positions ####
if st.button("Submit", key="submit"):
    update_exp_positions(exp_client, body_soup)







