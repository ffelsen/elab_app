import streamlit as st
import os
from utils import *
from elabapi_python import ItemsApi, ExperimentsApi
from inputparsing import *
from bs4 import BeautifulSoup
from warnings import filterwarnings
filterwarnings('ignore')

### Define Sample ####
st.title("Define Sample")

## Make sure an experiment is selected
if not st.session_state["exp_id"]:
    st.warning("please select an experiment")
    st.stop()

## data for selected Sample is stored here
step_data = {
    "name": "",
    "plate_material": "",
    "comment": "",
    "id": 0,
    "linked_exps": [],
    "samples": [],
}

#### update function ####
def update_exp_sample(exp_client, body_soup):
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
            li.decompose()

    ## inset new Positions
    for i, sample in enumerate(step_data["samples"]):
        ## create html tags
        txt = f"{sample.title}"
        new_li = body_soup.new_tag('li')
        new_b = body_soup.new_tag('strong')
        new_b.string = f"Sample {i+1}"
        href = f"{st.session_state['host_domain']}/database.php?mode=view&id={sample.id}"
        a_tag = body_soup.new_tag('a', href=href, **{'class': 'smpl'})
        pos_div = body_soup.new_tag('div', **{'class': 'smpl', 'style': 'display: inline;'})
        pos_div.string = txt + f" (ID: {sample.id})"
        ## stick tags together
        a_tag.append(pos_div)
        new_li.append(new_b)
        new_li.append(": ")
        new_li.append(a_tag)
        ## insert into html
        if last_resc_li:
            last_resc_li.insert_after(new_li)
            last_resc_li = new_li
        else:
            resc_ul.append(new_li)
            last_resc_li = new_li

    ## patch experiment with new body
    response = exp_client.patch_experiment(st.session_state["exp_id"], body={ 'body': str(body_soup) })

#### Get Data ####
## get linked samlpes
exp_names, exp_ids, exps = get_experiments(st.session_state['api_client'])
exp_client = ExperimentsApi(st.session_state["api_client"])
experiment = exp_client.get_experiment(st.session_state["exp_id"])
current_links = experiment.items_links or []
sample_titles_old = [ item_link.title for item_link in current_links]

## get more details
items_client = ItemsApi(st.session_state["api_client"])
sample = None
unlinked_titles = [""]
for item in items_client.read_items():
    if item.title not in sample_titles_old:
        unlinked_titles.append(item.title)
    else:
        step_data["samples"].append(item)
        print(item)
        
## get Sample Data
def get_data(sample, exp_client):
    global step_data
    if sample:
        body_soup = BeautifulSoup( sample.body or "" , 'html.parser') or ""
        try:
            step_data['plate_material'] = body_soup.find("div", class_="material").text
            step_data['comment'] = body_soup.find("div", class_="comment").text
        except AttributeError as e:
            st.info(f"possibly missing Sample Information?")
        step_data['name'] = sample.title
        step_data['id'] = sample.id
        step_data["linked_exps"] = []
        for exp_id in exp_ids:
            exp = exp_client.get_experiment(exp_id)
            for items_link in exp.items_links:
                if items_link.title==sample.title:
                    step_data["linked_exps"].append(exp_id)
        st.session_state["sample_id"] = step_data['id']
        return body_soup
    else:
        st.session_state["sample_id"] = None
        return BeautifulSoup( "", 'html.parser')

## make sure experiment has a resource section 
exp_soup = BeautifulSoup(experiment.body or "", 'html.parser')
if not exp_soup.find('div', class_='resc'):
    html_new = (
        "<div class='resc'>"
        "<hr>"
        "<h5><strong>Resources:<strong></h5>"
        "<ul>"
        "</ul>"
        "<hr>"
        "</div>")
    new_soup = BeautifulSoup(html_new or "", 'html.parser')
    dscrpt_p = exp_soup.find('p', class_='dscrpt')
    if dscrpt_p:
        dscrpt_p.insert_after( new_soup )
    else:
        if exp_soup.contents:
            exp_soup.contents[0].insert_before( new_soup )
        else:
            exp_soup.append( new_soup )

#### Select Sample ####
## select an already linked sample
col_old_smpl, col_old_del = st.columns(2)
with col_old_smpl:
    sample_title_old = st.selectbox("Select linked Sample to Edit:", sample_titles_old)
    for item in items_client.read_items():
        if item.title == sample_title_old:
            sample = item
with col_old_del:
    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    if st.button("⛓️‍💥 Unlink", key="butt_unlink"):
        if sample_title_old in sample_titles_old:
            response = exp_client.api_client.call_api(
                f"/experiments/{st.session_state['exp_id']}/items_links/{sample.id}",
                "DELETE",
                body=None,
                response_type=None,
                auth_settings=["apiKey"]
            )
            for i, smpl in enumerate(step_data["samples"]):
                if smpl.id==sample.id:
                    del step_data["samples"][i]
            update_exp_sample(exp_client, exp_soup)
            st.rerun()

## link another sample to experiment
col_link_smpl, col_link_yes = st.columns(2)
with col_link_smpl:
    sample_title_link = st.selectbox("Select another Sample to Link:", unlinked_titles, index=0)
    for item in items_client.read_items():
        if item.title == sample_title_link:
            sample2 = item
with col_link_yes:
    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    if st.button("🔗 Link", key="butt_link"):
        if sample_title_link in unlinked_titles:
            response = exp_client.api_client.call_api(
                f"/experiments/{st.session_state['exp_id']}/items_links/{sample2.id}",
                "POST",
                body=None,
                response_type=None,
                auth_settings=["apiKey"]
            )
            step_data["samples"].append(sample2)
            update_exp_sample(exp_client, exp_soup)
            st.rerun()

## create a New Sample
st.markdown("**Note**: use eLab to create New Sample ('Defaut' Resource), then you can Link and Edit it here.")

#### Edit Sample ####
body_soup = get_data(sample, exp_client)
st.markdown("---")

## set name
step_data["name"] = st.text_input("Sample Name:", value=step_data["name"])

## set plate
plate_options = ["Stainless Steel", "Molybdenum", "Tantalum"]
idx = get_index( plate_options, step_data["plate_material"], dflt=0 )
step_data["plate_material"] = st.selectbox("Plate Material:", plate_options, index=idx )

## set comment
step_data['comment'] = st.text_area("📝 Optional Note:", value=step_data["comment"])

## upload image of sample
sample_img = st.file_uploader("📷 Upload Sample Image", type=["png", "jpg", "jpeg"])

#### Update Sample ####
if st.button("Submit", key="submit"):
    ## always start with these general infos
    new_html = ("<div class='fixed_layout'>"
        "<hr>"
        "<h3>Sample Information</h3>"
        "<ul>"
        f"<li><b>Sample ID</b>: <div class='sample_id' style='display:inline;'>{step_data['id']}</div></li>"
        f"<li><b>Sample Name</b>: <div class='name' style='display:inline;'>{step_data['name']}</div></li>"
        f"<li><b>Plate Material</b>: <div class='material' style='display:inline;'>{step_data['plate_material']}</div></li>"
        f"<li><b>Comment</b>: <div class='comment' style='display:inline;'>{step_data['comment']}</div></li>"
        "</ul>"
        "<hr>"
        "<h3>Linked Experiments</h3>"
        "<ul>")
    for i, exp_id in enumerate(step_data["linked_exps"]):
        exp = exp_client.get_experiment(exp_id)
        new_html += f"<li><b>Experiment {i+1}</b>: <a href='{st.session_state['host_domain']}/experiments.php?mode=view&id={exp_id}'>{exp.title}</a></li>"
    new_html += ("</ul>"
        "<hr>"
        "</div>")
    
    ## remove the old general infos from the current html
    body_soup = BeautifulSoup(sample.body or "", 'html.parser')
    for div in body_soup.find_all("div", class_="fixed_layout"):
        div.decompose()
    
    ## add any additional infos that may be in the current html
    new_html += str(body_soup)
    
    ## update the sample
    items_client.patch_item(step_data['id'], body={"body": new_html})






