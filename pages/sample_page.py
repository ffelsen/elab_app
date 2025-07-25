import streamlit as st
from utils import *
from elabapi_python import ItemsApi, ExperimentsApi
from inputparsing import *
from bs4 import BeautifulSoup
from warnings import filterwarnings
#filterwarnings('ignore')
import os

#### Define Sample ####
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


#### Get Data ####
## api
exp_client = ExperimentsApi(st.session_state["api_client"])
items_client = ItemsApi(st.session_state["api_client"])

## (Note: get list of dict)
linked_samples = get_linked_resources(st.session_state['api_client'],st.session_state["exp_id"])
linked_sample_ids = [ iteml['id'] for iteml in linked_samples ]
##  (Note: .read_items() returns list of Item)
all_samples = ItemsApi(st.session_state["api_client"]).read_items()
all_sample_ids = [ item.id for item in all_samples]

## get linked and unlinked samples
linked_samples = []
unlinked_samples = []
for i,sample_id in enumerate(all_sample_ids):
    if sample_id in linked_sample_ids:
        linked_samples.append(all_samples[i])
    else:
        unlinked_samples.append(all_samples[i])
all_samples = None

## generate titles
linked_sample_titles = [ f"{item.title} (ID: {item.id})" for item in linked_samples]
unlinked_sample_titles = [ f"{item.title} (ID: {item.id})" for item in unlinked_samples]

## sample
sample = None

## get Sample Data
def get_sample_data(exp_client, sample):
    data = {
        "id":None,
        "title":None,
        "body":"",
        "plate_mat":"",
        "comment":"",
        "linked_exps":[]
    }
    if sample==None: return data
    data['id'] = sample.id
    data['title'] = sample.title
    data['body'] = sample.body
    if sample:
        body_soup = BeautifulSoup( sample.body or "" , 'html.parser')
        try:
            data['plate_mat'] = body_soup.find("div", class_="material").text
            data['comment'] = body_soup.find("div", class_="comment").text
        except AttributeError as e:
            st.info(f"possibly missing Sample Information?")
        exp_names, exp_ids, exps = get_experiments(st.session_state['api_client'])
        for exp_id in exp_ids:
            linked_items = get_linked_resources(st.session_state['api_client'],exp_id)
            for item_link in linked_items:
                if item_link['id']==sample.id:
                    data["linked_exps"].append(exp_id)
    
    return data

## make sure experiment has a resource section 
experiment = exp_client.get_experiment(st.session_state["exp_id"])
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
    selected_old_title = st.selectbox("Select linked Sample to Edit:", linked_sample_titles)
    idx = get_index(linked_sample_titles, selected_old_title)
    if idx!=-1:
        sample = linked_samples[idx]
        st.session_state["sample_id"] = sample.id
with col_old_del:
    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    if st.button("⛓️‍💥 Unlink", key="butt_unlink"):
        if selected_old_title in linked_sample_titles:
            unlink_sample_from_exp(exp_client, st.session_state["exp_id"], sample.id)
            idx = get_index(linked_sample_titles, selected_old_title)
            del linked_samples[idx]
            experiment_patch_samples(exp_client, st.session_state["exp_id"], exp_soup, linked_samples)
            st.rerun()

## link another sample to experiment
col_link_smpl, col_link_yes = st.columns(2)
with col_link_smpl:
    selected_unlinked_title = st.selectbox("Select another Sample to Link:", unlinked_sample_titles, index=0)
    idx = get_index(unlinked_sample_titles, selected_unlinked_title)
    if idx!=-1:
        sample2 = unlinked_samples[idx]
with col_link_yes:
    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    if st.button("🔗 Link", key="butt_link"):
        if selected_unlinked_title in unlinked_sample_titles:
            link_sample_to_exp(exp_client, st.session_state["exp_id"], sample2.id)
            linked_samples.append(sample2)
            idx = get_index(unlinked_sample_titles, selected_unlinked_title)
            del unlinked_samples[idx]
            experiment_patch_samples(exp_client, st.session_state["exp_id"], exp_soup, step_data["samples"])
            st.rerun()

## create a New Sample
st.markdown("**Note**: use eLab to create New Sample ('Defaut' Resource), then you can Link and Edit it here.")

#### Edit Sample ####
if sample == None: st.stop()
st.markdown("---")
sample_data = get_sample_data(exp_client, sample)

## set name
sample_data["title"] = st.text_input("Sample Name:", value=sample_data["title"])

## set plate
plate_options = ["Stainless Steel", "Molybdenum", "Tantalum"]
idx = get_index( plate_options, sample_data["plate_mat"], default=0 )
sample_data["plate_mat"] = st.selectbox("Plate Material:", plate_options, index=idx )

## set comment
sample_data["comment"] = st.text_area("📝 Optional Note:", value=sample_data["comment"])

## upload image of sample
sample_img = st.file_uploader("📷 Upload Sample Image", type=["png", "jpg", "jpeg"])

#### Update Sample ####
if st.button("Submit", key="submit"):
    ## always start with these general infos
    new_html = ("<div class='fixed_layout'>"
        "<hr>"
        "<h3>Sample Information</h3>"
        "<ul>"
        f"<li><b>Sample ID</b>: <div class='sample_id' style='display:inline;'>{sample_data['id']}</div></li>"
        f"<li><b>Sample Name</b>: <div class='name' style='display:inline;'>{sample_data['title']}</div></li>"
        f"<li><b>Plate Material</b>: <div class='material' style='display:inline;'>{sample_data['plate_mat']}</div></li>"
        f"<li><b>Comment</b>: <div class='comment' style='display:inline;'>{sample_data['comment']}</div></li>"
        "</ul>"
        "<hr>"
        "<h3>Linked Experiments</h3>"
        "<ul>")
    for i, exp_id in enumerate(sample_data["linked_exps"]):
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
    items_client.patch_item(sample_data['id'], body={"body": new_html})
    
    ## add image
    if sample_img:
        ## save locally
        save_success = False
        if st.session_state.get("file_path"):
            save_dir = st.session_state["file_path"]
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, sample_img.name)
            with open(save_path, "wb") as f:
                f.write(sample_img.getvalue())
            st.success(f"📷 Image saved locally to: {save_path}")
            save_success = True
        else:
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(sample_img.name)[1]) as tmp:
                tmp.write(sample_img.getvalue())
                save_path = tmp.name
            st.info("🖼️ No path provided – image uploaded to ELN only (not saved locally)")
        ## Upload to ELN
        if upload_image(st.session_state.api_client, st.session_state.exp_id, save_path):
            insert_image(st.session_state.api_client, st.session_state.exp_id, os.path.basename(sample_img.name))
            st.success("☁️ Image uploaded to eLabFTW (added to Experiment)")
        else:
            st.error("❌ Upload to eLabFTW failed")
            if not save_success:
                os.remove(save_path)






