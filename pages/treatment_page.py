import streamlit as st
from utils import *
from elabapi_python import ItemsApi, ExperimentsApi
from inputparsing import *
from bs4 import BeautifulSoup
from warnings import filterwarnings
filterwarnings('ignore')

#### Initial Setup ####
## Make sure an Experiment is selected
if not st.session_state["exp_id"]:
    st.warning("please select an Experiment.")
    st.stop()
## Make sure a Sample is selected
if not st.session_state["sample_id"]:
    st.warning("please select a Sample. (may need to load sample first)")
    st.stop()

## constants etc...
cond_classes = ['temp0', 'temp', 'gases', 'ramp', 'xenergy', 'dura', 'comment']
cond_names = ["Initial Temperature", "Constant Temperature", "Set Gas Compesition", "Heating Ramp", "Ion Energy", "Duration", "Comment"]

#### helper functions ####
## get treatment steps from experiments html
def get_treat_steps(body_soup):
    treat_sections = body_soup.find_all('div', class_=['sputter', 'anneal'])
    st.write()
    steps = []
    
    for treat in treat_sections:
        typ = treat['class'][0]
        data = {'title':"", 'typ':typ, 'num':-1, 'conditions':[], 'note':"" }
        ## get title and note
        title_tag = treat.find('div', class_='title')
        note_tag = treat.find('div', class_='note')
        if title_tag:
            data['title'] = title_tag.get_text(strip=True).rstrip(":")
            try:
                data['num'] = int(data['title'].split('#')[1].strip())
            except IndexError:
                continue
        if note_tag:
            data['note'] = note_tag.get_text(strip=True)
        ## get conditions [ ["temp0", "298 K"], ["gases", "..."], ... ]
        for div in treat.find_all('div'):
            classes_div = div.get('class', [])
            for clss in classes_div:
                if clss in cond_classes:
                    value = div.get_text(strip=True)
                    data['conditions'].append([clss,value])
        
        steps.append(data)
    return steps
    
## generate new html for treatment step
def treatment_html(treat):
    # sample_ref_idx --> Sample {sample_ref_idx+1}
    # treat := {'title':"Anneal #1", 'typ':"anneal", 'num':1, 'conditions':[], 'note':"Nothing unusual." }
    # treat["conditions"] := [ ("temp0", 298), ("gases", {'N2':2e-5, 'O2':1e-6 } ), ("ramp", { 'typ':0, 'start':0.2, 'stop':20, 'step':0.002 }), ("ramp", { 'typ':1, 'start':700, 'stop':1000, 'step':1 }), ... ]
    html = []
    html.append(f'<div class="{treat["typ"]}">')
    html.append(f'<b><div class="title" style="display:inline;">{treat["title"]}</div>:</b>')
    html.append(f'<a>(<div class="sample" style="display:inline;">Sample {sample_ref_idx}</div>)</a>')

    # list of diffrent conditions ( 'temp0', 'temp', 'gases', 'ramp', 'xenergy', 'dura', 'comment' ) 
    html.append('<ul>')
    for cond_type, cond_val in treat["conditions"]:
        if cond_type == "temp0":
            html.append(f'<li><b>Initial Temp.</b>: <div class="temp0" style="display:inline;">{cond_val} K</div></li>')
            
        elif cond_type == "temp":
            html.append(f'<li><b>Const. Temp.</b>: <div class="temp" style="display:inline;">{cond_val} K</div></li>')
            
        elif cond_type == "gases":
            gas_list = ", ".join([f"{g} ({v:.1e} mbar)" for g, v in cond_val.items()])
            if gas_list == "":
                gas_list = "UHV"
            html.append(f'<li><b>Set Gases</b>: <div class="gases" style="display:inline;">{gas_list}</div></li>')
            
        elif cond_type == "ramp":
            typ = cond_val.get("typ", 0)
            units = "W" if typ == 0 else "K"
            rate_unit = "W/s" if typ == 0 else "K/s"
            ramp_line = f'{cond_val["start"]} {units} &#8614; {cond_val["stop"]} {units}; @ {cond_val["step"]} {rate_unit}'
            label = "Ramp Power" if typ == 0 else "Ramp Temperature"
            html.append(f'<li><b>{label}</b>: <div class="ramp" style="display:inline;">{ramp_line}</div></li>')
            
        elif cond_type == "xenergy":
            html.append(f'<li><b>Ion Energy</b>: <div class="xenergy" style="display:inline;">{cond_val["U"]} V ({cond_val["I"]} mA)</div></li>')
            
        elif cond_type == "dura":
            html.append(f'<li><b>Duration</b>: <div class="{cond_type}" style="display:inline;">{cond_val}</div></li>')
        else:
            html.append(f'<li><b>{cond_type}</b>: <div class="{cond_type}" style="display:inline;">{cond_val}</div></li>')
    html.append('</ul>')
    
    ## almost done
    note = treat.get("note", "")
    if note:
        html.append(f'<small><b>Note</b>: <div class="note" style="display:inline;">{note}</div></small>')
    html.append('</div>')
    return "\n".join(html)

## convert the treatments conditions into the correct format
def parse_treatment(treat):
    ## treat["conditions"] = [ ("temp0", "298 K"), ("gases", "..."), ... ]
    for i, cond in enumerate(treat["conditions"]):
        value = treat["conditions"][i][1]
        if cond[0] in ["temp0", "temp"]:
            # what i have "298 K"
            try:
                treat["conditions"][i][1] = float(value.split()[0])
            except Exception:
                treat["conditions"][i][1] = None
            # should be 298.0
        elif cond[0]=="gases": 
            # what i have "N2 (2.0e-5 mbar), O2 (1.0e-6 mbar)"
            treat["conditions"][i][1] = {}
            value = value.strip().split(",")
            for term in value:
                term = term.split("(")
                gas = term[0].strip()
                try:
                    pressure = float(term[1].rstrip(")").split(" ")[0])
                    treat["conditions"][i][1][gas] = pressure
                except IndexError:
                    pressure = 0.0
            # should be { 'N2':2.0e-5, 'O2':1.0e-6 }
        elif cond[0]=="ramp":
            # what i have "0.2 W &#8614; 20 W; @ 0.002 W/s"
            treat["conditions"][i][1] = { 'typ':0, 'start':0.0, 'stop':0.0, 'step':0.0 }
            value = value.strip().replace("&#8614;", '↦').split('↦')
            value[0] = value[0].strip()
            start = value[0].split(" ")[0]
            treat["conditions"][i][1]['start'] = start
            try:
                unit = value[0][-1]
                if unit=="K":
                    treat["conditions"][i][1]['typ'] = 1
            except IndexError:
                unit = "W"
            try:
                value[1] = value[1].strip()
                stop = float(value[1].split(" ")[0])
                treat["conditions"][i][1]['stop'] = stop
                step = float(value[1].split("@")[1].strip().split(" ")[0])
                treat["conditions"][i][1]['step'] = step
            except IndexError:
                continue
            # should be { 'typ':0, 'start':0.2, 'stop':20, 'step':0.002 }
        elif cond[0]=="dura": 
            # what i have "1 h, 30 min, 5 s"
            pass 
            # this is fine
        elif cond[0]=="xenergy":
            # what i have "4 V (20 mA)"
            treat["conditions"][i][1] = {}
            value = value.split('(')
            U = 0.0
            I = 0.0
            try:
                U = float(value[0].strip().split(" ")[0])
                I = float(value[1].strip().split(" ")[0])
            except ValueError:
                continue
            treat["conditions"][i][1]['U'] = U
            treat["conditions"][i][1]['I'] = I
            # this is should be { 'U':4.0, 'I':20 }
        elif cond[0]=="comment": 
            # what i have "..."
            pass 
            # this is fine
    return treat

## remove treatment step from experiments html
def remove_step_entry(body_soup, title, typ):
    ## look in all divs of the same step typ, if title same delete the parent table row
    print("DELETE:","title:",title,"typ",typ)
    for mydiv in body_soup.find_all('div', class_=typ):
        title_div = mydiv.find('div', class_='title')
        if title_div:
            title_txt = title_div.get_text(strip=True).strip()
            if title_txt == title:
                tr = mydiv.find_parent("tr")
                if tr:
                    tr.decompose()
    return body_soup
    
## update treatment step in experiment
def update_exp_treat(exp_client, body_soup, treat):
    new_html = treatment_html(treat)
    new_soup = BeautifulSoup(new_html or "", 'html.parser').div
    
    ## replace treatment step
    for mydiv in body_soup.find_all('div', class_=treat["typ"]):
        title_div = mydiv.find('div', class_='title')
        if title_div:
            title_txt = title_div.get_text(strip=True).strip()
            if title_txt == treat["title"]:
                mydiv.replace_with(new_soup)
    
    ## patch experiment
    response = exp_client.patch_experiment(st.session_state["exp_id"], body={ 'body': str(body_soup) })

#### Get Data from Experiment ####
## get experiment
exp_client = ExperimentsApi(st.session_state["api_client"])
experiment = exp_client.get_experiment(st.session_state["exp_id"])

## get sample
items_client = ItemsApi(st.session_state["api_client"])
sample = items_client.get_item(st.session_state["sample_id"])
current_links = experiment.items_links or []
sample_titles_old = [ item_link.title for item_link in current_links ]
sample_ref_idx = -1
for i, title in enumerate(sample_titles_old):
    if title==sample.title:
        sample_ref_idx = i+1
        break

## get treatment steps in experiment
body_soup = BeautifulSoup( experiment.body or "", 'html.parser')
all_treatments = get_treat_steps(body_soup)

#### Setup for Selecting and loading Treatment step ####
if ("selected_treatment" not in st.session_state)or(st.session_state['selected_treatment']==None):
    st.session_state['selected_treatment'] = { 'title':None, 'typ':None, 'conditions':[], 'note':None }
if "treat_index" not in st.session_state:
    st.session_state['treat_index'] = -1
else:
    selected_index = st.session_state['treat_index']
if "reload_treatmant" not in st.session_state:
    st.session_state["reload_treatmant"] = True
if "cond_input_keys" not in st.session_state:
    st.session_state["cond_input_keys"] = []

#### User Interface ####
st.title("Treatments steps")

## select old treatment
options_typs = ["Sputtering","Annealing"]
classes_typs = ["sputter","anneal"]
options_titles = [ treat["title"] for treat in all_treatments]
selected_index = -1
selected_typi = -1

# select (old),  typ (new), reload (old), delete (old),create (new)
col_old_treat, col_new_typ, col_reload, col_old_del, col_new_yes = st.columns([6,5,2,3,3])

with col_old_treat:
    selected_index = get_index(options_titles,st.selectbox('Treatment:', options_titles, index=st.session_state['treat_index'] if not -1 else 0, key="treat_old"))
    if (selected_index!=-1)and((selected_index!=st.session_state["treat_index"])or(st.session_state["reload_treatmant"])):
        ## get treatment data parsed
        st.session_state["treat_index"] = selected_index
        st.session_state["selected_treatment"] = parse_treatment(all_treatments[selected_index])
        st.session_state["reload_treatmant"] = False
        ## clear treatment input keys
        for key in st.session_state["cond_input_keys"]:
            del st.session_state[key]
        st.session_state["cond_input_keys"] = []

with col_new_typ:
    selected_typi = get_index(options_typs, st.selectbox('Typ:', options_typs, key="typ_new"))
    
with col_reload:
    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    if st.button("🔄", key="butt_reload"):
        ## clear data from old condition inputs
        st.session_state["reload_treatmant"] = True
        st.rerun()
        
        
with col_old_del:
    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    if st.button("❌ Delete", key="butt_delete"):
        if selected_index!=-1:
            print("DELETE TREATMENT!!!!!!!")
            body_soup = remove_step_entry(body_soup, st.session_state['selected_treatment']["title"], st.session_state['selected_treatment']["typ"])
            response = exp_client.patch_experiment(st.session_state["exp_id"], body={ 'body': str(body_soup) })
            st.session_state['selected_treatment'] = { 'title':None, 'typ':None, 'conditions':[], 'note':None }
            st.session_state['treat_index'] = -1
            st.rerun()
            
with col_new_yes:
    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    if st.button("➕ Create", key="butt_create"):
        typ = classes_typs[selected_typi]
        name = options_typs[selected_typi]
        num = get_smallest_available([ treat["num"] for treat in all_treatments])
        my_html = (
            f"<div class='{typ}'>"
            f"<h5><div class='title' style='display:inline;'>{name} #{num}</div>: <a><div class='sample' style='display:inline;'>( Sample {sample_ref_idx} )</div></a></h5><br>"
            "<ul>"
            "</ul>"
            "</div>")
        append_to_experiment(st.session_state["api_client"], st.session_state["exp_id"], my_html)
        st.rerun()

st.markdown("---")


## list conditions
should_reload = True
# conditions = [ ("temp0", "298 K"), ("gases", "..."), ... ]

if st.session_state["treat_index"]!=-1:
    for i in range(0, len(st.session_state['selected_treatment']['conditions'])):
        cond_typ = st.session_state["selected_treatment"]["conditions"][i][0]
        col_cond, col_del = st.columns([11,1])
        with col_cond:
            ## get input class
            if cond_typ == "gases":
                cond = GasComposer(key=f"{i}")
            elif cond_typ == "ramp":
                cond = HeatingRamp(key=f"{i}")
            elif cond_typ == "comment":
                cond = RetractableComment(key=f"{i}")
            elif cond_typ == "temp0":
                cond = PhysicalQuantityInput(key=f"{i}", label="Const. Temperature:", units="K")
            elif cond_typ == "temp":
                cond = PhysicalQuantityInput(key=f"{i}", label="Const. Temperature:", units="K")
            elif cond_typ == "dura":
                cond = DurationCondition(key=f"{i}")
            elif cond_typ == "xenergy":
                cond = IonEnergyCondition(key=f"{i}")
            else:
                cond = None
            ## update treatment condition
            if cond!=None:
                if (cond.key not in st.session_state["cond_input_keys"]):
                    cond.set_data(st.session_state["selected_treatment"]["conditions"][i][1])
                    st.session_state["cond_input_keys"].append(cond.key)
                cond.render()
                st.session_state["selected_treatment"]["conditions"][i][1] = cond.get_data()
        with col_del:
            if st.button("❌", key=f"del_cond_{i}"):
                del st.session_state["selected_treatment"]["conditions"][i]
                st.rerun()

## add a new condition
new_cond_typ = -1
col_cond_sel, col_cond_yes = st.columns([3,2])
with col_cond_sel:
    new_cond_typ = get_index(cond_names,st.selectbox('Select Condition to Add:', cond_names, index=0, key="sel_cond"))
with col_cond_yes:
    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    if st.button("➕ Add Condition", key="new_cond"):
        if (st.session_state['treat_index']!=-1)and(new_cond_typ in range(0, len(cond_classes))):
            cond_class = cond_classes[new_cond_typ]
            if cond_class=="temp0":
                new_cond = [cond_class, 0.0]
            elif cond_class=="temp":
                new_cond = [cond_class, 0.0]
            elif cond_class=="gases":
                new_cond = [cond_class, {} ]
            elif cond_class=="ramp":
                new_cond = [cond_class, { 'typ':0, 'start':0.0, 'stop':0.0, 'step':0.0 } ]
            elif cond_class=="xenergy":
                new_cond = [cond_class, { 'U':0.0, 'I':20.0} ]
            elif cond_class=="dura":
                new_cond = [cond_class, ""]
            elif cond_class=="comment":
                new_cond = [cond_class, ""]
            else:
                new_cond = None
            if new_cond!=None:
                st.session_state["selected_treatment"]["conditions"].append(new_cond)
                st.rerun()
            
#### Update Step ####
st.markdown("---")
if st.button("Update Treatment step", key="submit"):
    if selected_index!=-1:
        update_exp_treat(exp_client, body_soup, st.session_state["selected_treatment"])
        st.rerun()

    
