import streamlit as st
from utils import *
from elabapi_python import ItemsApi, ExperimentsApi
from inputparsing import *
from bs4 import BeautifulSoup
from warnings import filterwarnings
filterwarnings('ignore')

default_mess = {
    'title':None,
    'typ':None,
    'excite':None,
    'spot':None,
    'power':0.0,
    'voltage':0.0,
    'corelvls':[],
    'gases':{},
    'maxcps':0.0,
    'refpeak':"",
    'pos':None,
    'conditions':[],
    'note':None,
    'num':-1
}

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
cond_classes = ['excite', 'xsource', 'spot', 'pos', 'gases', 'maxcps', 'corelvls', 'dura', 'temp', 'temp_p', 'ramp', 'comment']
cond_names = [ "Excitation Energy", "X-Ray Source", "Beam Spot Size", "Position", "Set Gas", "Max. CPS", "Core Levels", "Duration", "Const. Temperature", "Plate Temperature", "Heating Ramp", "Comment"]
#### helper functions ####
## get #number for new treatment step
def get_smallest_available(nums):
    n = 1
    while n in nums:
        n += 1
    return n

## get treatment steps from experiments html
def get_mess_steps(body_soup):
    treat_sections = body_soup.find_all('div', class_=['mess_ref', 'mess'])
    st.write()
    steps = []
    
    for treat in treat_sections:
        data = {
            'title':"",
            'typ':"",
            'excite':"",
            'spot':"",
            'power':"",
            'voltage':"",
            'corelvls':"",
            'gases':"",
            'maxcps':"",
            'refpeak':"",
            'pos':"",
            'conditions':[],
            'note':"",
            'num':-1
        }
        typ = treat['class'][0]
        data["typ"] = typ
        ## get title and note
        title_tag = treat.find('div', class_='title')
        title_tag = treat.find('div', class_='title')
        excite_tag = treat.find('div', class_='excite')
        spot_tag = treat.find('div', class_='spot')
        power_tag = treat.find('div', class_='power')
        voltage_tag = treat.find('div', class_='voltage')
        corelvls_tag = treat.find('div', class_='corelvls')
        maxcps_tag = treat.find('div', class_='maxcps')
        refpeak_tag = treat.find('div', class_='refpeak')
        pos_tag = treat.find('div', class_='pos')
        note_tag = treat.find('div', class_='note')
        if title_tag:
            data['title'] = title_tag.get_text(strip=True).rstrip(":")
            try:
                data['num'] = int(data['title'].split('#')[1].strip())
            except IndexError:
                continue
        if excite_tag:
            data['excite'] = excite_tag.get_text(strip=True)
        if spot_tag:
            data['spot'] = spot_tag.get_text(strip=True)
        if power_tag:
            data['power'] = power_tag.get_text(strip=True)
        if corelvls_tag:
            data['corelvls'] = corelvls_tag.get_text(strip=True)
        if maxcps_tag:
            data['maxcps'] = maxcps_tag.get_text(strip=True)
        if voltage_tag:
            data['voltage'] = voltage_tag.get_text(strip=True)
        if pos_tag:
            data['pos'] = pos_tag.get_text(strip=True)
        if note_tag:
            data['note'] = note_tag.get_text(strip=True)
        ## get conditions [ ["temp0", "298 K"], ["gases", "..."], ... ]
        gases_count = 0
        for div in treat.find_all('div'):
            classes_div = div.get('class', [])
            for clss in classes_div:
                if clss in cond_classes:
                    value = div.get_text(strip=True)
                    if (clss=="gases")and(gases_count==0):
                        data['gases'] = value
                        gases_count+=1
                    else:
                        data['conditions'].append([clss,value])
        steps.append(data)
    return steps
    
## generate new html for treatment step
def mess_html(treat):
    print(treat)
    html = []
    html.append(f'<div class="{treat["typ"]}">')
    html.append(f'<b><div class="title" style="display:inline;">{treat["title"]}</div>:</b>')
    html.append(f'<a>(<div class="sample" style="display:inline;">Sample {sample_ref_idx}</div>)</a>')
    
    ## mandatory conditions
    html.append('<ul>')
    html.append(f'<li><b>Excitation Energy</b>: <div class="excite" style="display:inline;">{treat["excite"]}</div></li>')
    html.append(f'<li><b>Spot Setting</b>: <div class="spot" style="display:inline;">{treat["spot"]}</div></li>')
    html.append(f'<li><b>Power</b>: <div class="power" style="display:inline;">{treat["power"]} W</div></li>')
    html.append(f'<li><b>Voltage</b>: <div class="voltage" style="display:inline;">{treat["voltage"]} V</div></li>')
    if treat["typ"]=="mess_ref":
        html.append(f'<li><b>Max. CPS</b>: <div class="maxcps" style="display:inline;">{treat["maxcps"]}</div></li>')
        html.append(f'<li><b>Refrance Peak</b>: <div class="refpeak" style="display:inline;">{treat["refpeak"]}</div></li>')
    else:
        html.append(f'<li><b>Core Levels</b>: <div class="corelvls" style="display:inline;">{", ".join(treat["corelvls"])} V</div></li>')
    html.append(f'<li><b>Set Gas</b>: <div class="gases" style="display:inline;">{", ".join([f"{g} ({v:.1e} mbar)" for g, v in treat["gases"].items()])}</div></li>')
    html.append(f'<li><b>Position</b>: <div class="pos" style="display:inline;">{treat["pos"]} V</div></li>')

    # list of optional conditions ['gases', 'maxcps', 'corelvls', 'dura', 'temp', 'temp_p', 'ramp', 'comment']
    for cond_type, cond_val in treat["conditions"]:
        if cond_type == "temp":
            html.append(f'<li><b>Const. Temprature</b>: <div class="{cond_type}" style="display:inline;">{cond_val} K</div></li>')
        
        elif cond_type == "temp_p":
            html.append(f'<li><b>Plate Temprature</b>: <div class="{cond_type}" style="display:inline;">{cond_val} K</div></li>')
            
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

## convert the messurement conditions into the correct format
def parse_mess(treat):
    ## treat["conditions"] = [ ("temp0", "298 K"), ("gases", "..."), ... ]
    value = treat["gases"].strip().split(",")
    treat["gases"] = {}
    for term in value:
        term = term.split("(")
        gas = term[0].strip()
        try:
            pressure = float(term[1].rstrip(")").split(" ")[0])
            treat["gases"][gas] = pressure
        except IndexError:
            continue
    treat["corelvls"] = treat["corelvls"].strip().split(",")
    
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
        elif cond[0]=="xsource":
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
def update_exp_step(exp_client, body_soup, step):
    new_html = mess_html(step)
    new_soup = BeautifulSoup(new_html or "", 'html.parser').div
    print(new_html)
    
    ## replace treatment step
    for mydiv in body_soup.find_all('div', class_=step["typ"]):
        title_div = mydiv.find('div', class_='title')
        if title_div:
            title_txt = title_div.get_text(strip=True).strip()
            if title_txt == step["title"]:
                mydiv.replace_with(new_soup)
    
    ## patch experiment
    response = exp_client.patch_experiment(st.session_state["exp_id"], body={ 'body': str(body_soup) })
    #print(response)

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
all_messes = get_mess_steps(body_soup)

#### Setup for Selecting and loading Treatment step ####

if ("selected_mess" not in st.session_state)or(st.session_state['selected_mess']==None):
    st.session_state['selected_mess'] = default_mess
if "mess_index" not in st.session_state:
    st.session_state['mess_index'] = -1
else:
    selected_index = st.session_state['mess_index']
if "reload_mess" not in st.session_state:
    st.session_state["reload_mess"] = True
if "cond_input_keys" not in st.session_state:
    st.session_state["cond_input_keys"] = []

#### User Interface ####
st.title("Measurement Steps")

## select old treatment
options_typs = ["Reference Measurement","Measurement"]
classes_typs = ["mess_ref","mess"]
options_titles = [ mess["title"] for mess in all_messes]
selected_index = -1
selected_typi = -1

# select (old),  typ (new), reload (old), delete (old),create (new)
col_old_treat, col_new_typ, col_reload, col_old_del, col_new_yes = st.columns([8,6,2,2,3])

with col_old_treat:
    selected_index = get_index(options_titles,st.selectbox('Measurement:', options_titles, index=st.session_state['mess_index'] if not -1 else 0, key="mess_old"))
    if (selected_index!=-1)and((selected_index!=st.session_state["mess_index"])or(st.session_state["reload_mess"])):
        ## get treatment data parsed
        st.session_state["mess_index"] = selected_index
        st.session_state["selected_mess"] = default_mess
        st.session_state["selected_mess"] = parse_mess(all_messes[selected_index])
        st.session_state["reload_mess"] = False
        ## clear treatment input keys
        for key in st.session_state["cond_input_keys"]:
            del st.session_state[key]
        st.session_state["cond_input_keys"] = []

with col_new_typ:
    selected_typi = get_index(options_typs, st.selectbox('Typ:', options_typs, key="typ_new"))
    
with col_reload:
    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    if st.button("🔄", key="butt_reload", help="Reload Measurement Step"):
        ## clear data from old condition inputs
        st.session_state["reload_mess"] = True
        st.rerun()
        
        
with col_old_del:
    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    if st.button("❌", key="butt_delete", help="Delete Selected Measurement"):
        if selected_index!=-1:
            body_soup = remove_step_entry(body_soup, st.session_state['selected_mess']["title"], st.session_state['selected_mess']["typ"])
            response = exp_client.patch_experiment(st.session_state["exp_id"], body={ 'body': str(body_soup) })
            st.session_state['selected_mess'] = default_mess
            st.session_state['mess_index'] = -1
            st.rerun()
            
with col_new_yes:
    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    if st.button("➕ New", key="butt_create",  help="Create New Measurement"):
        typ = classes_typs[selected_typi]
        name = options_typs[selected_typi]
        num = get_smallest_available([ mess["num"] for mess in all_messes])
        my_html = (
            f"<div class='{typ}'>"
            f"<h5><div class='title' style='display:inline;'>{name} #{num}</div>: <a><div class='sample' style='display:inline;'>( Sample {sample_ref_idx} )</div></a></h5><br>"
            "<ul>"
            "</ul>"
            "</div>")
        append_to_experiment(st.session_state["api_client"], st.session_state["exp_id"], my_html)
        st.rerun()

st.markdown("---")

## list conditions  removed "Mg K α₁ (1253.6 eV)", "Cu K α₁ (8047.8 eV)" since dont know spot settings
excitation_energies = ["Al K α₁ (1486.6 eV)", "Ag L α₁ (2984.3 eV)", "Cr K α₁ (5414.8 eV)"]
spot_settings = [["Al 120um 50W", "Al 250um 100W", "Al 330um 150W", "Al 70um 20W"],
["Ag 130um 25W", "Ag 260um 50W", "Ag 370um 75W", "Ag 500um 100W", "Ag 70um 10W"],
[ "Cr 200um 10W", "Cr 200um 10W (Energy = 23kV)", "Cr 200um 25W","Cr 330um 50W", "Cr 330um  50W (Energy = 23kV)", "Cr 430um 75W", "Cr 530um 100W"]]
VALID_ORBITALS = {
    "C":   ["1s"],
    "O":   ["1s"],
    "Ti":  ["2p", "2s"],
    "Ag":  ["3d", "3p"],
    "Pd":  ["3d", "3p"],
    "Al":  ["2p", "2s"],
    "Cr":  ["2p", "2s"],
    "Ni":  ["2p"],
    "Fe":  ["2p"],
    "Cu":  ["2p", "3p"],
    "Zn":  ["2p", "3p"],
    "Si":  ["2p", "2s"],
    "N":   ["1s"]
}

## mandatory fields { 'title':None, 'typ':None, 'excite':None, 'spot':None, 'power':0.0, 'voltage':0.0, 'corelvls':[], 'gases':{}, 'position':None, 'conditions':[], 'note':None }
col_exc, col_spot = st.columns(2)
with col_exc:
    old_idx = get_index(excitation_energies,st.session_state["selected_mess"]["excite"], default=0)
    excite = st.selectbox("Excitation Energy:", excitation_energies, index=old_idx, key="xray_exc")
    st.session_state["selected_mess"]["excite"] = excite
with col_spot:
    idx = get_index(excitation_energies,excite)
    if idx>=0:
        old_idx = get_index(spot_settings[idx],st.session_state["selected_mess"]["spot"], default=0)
        spot = st.selectbox("Spot:", spot_settings[idx], index=old_idx, key="xray_spot")
        st.session_state["selected_mess"]["spot"] = spot
    else:
        spot = st.selectbox("Spot:", [], key="xray_spot")
        st.session_state["selected_mess"]["spot"] = spot

col_pow, col_vol = st.columns(2)
with col_pow:
    power = float_text_input("xray_pow", "Power [W]", default=st.session_state["selected_mess"]["power"])
    st.session_state["selected_mess"]["power"] = power
with col_vol:
    voltage = float_text_input("xray_vol", "Voltage [kV]", default=st.session_state["selected_mess"]["voltage"])
    st.session_state["selected_mess"]["voltage"] = voltage

## Reference Measurement typ specific
if st.session_state['mess_index']!=-1:
    mess_typ = st.session_state['selected_mess']['typ']
elif selected_typi!=-1:
    mess_typ = classes_typs[selected_typi]

if mess_typ=="mess_ref":
    col_cps, col_ref = st.columns(2)
    with col_cps:
        max_cps = float_text_input("max_cps", "Max. CPS", default=st.session_state["selected_mess"]["maxcps"])
        st.session_state["selected_mess"]["maxcps"] = max_cps
    with col_ref:
        ref_peak = st.text_input("Reference Peak", placeholder="e.g., O₂ at 525 eV", value=st.session_state["selected_mess"]["refpeak"])
        st.session_state["selected_mess"]["refpeak"] = ref_peak
else:
    corelvls = CoreLevelsCondition( "corelvls", VALID_ORBITALS)
    corelvls.set_data(st.session_state["selected_mess"]["corelvls"])
    corelvls.render()
    st.session_state["selected_mess"]["corelvls"] = corelvls.get_data()
    
xgases = GasComposer(key=f"xgases")
xgases.set_data(st.session_state["selected_mess"]["gases"])
xgases.render()
st.session_state["selected_mess"]["gases"] = xgases.get_data()

##### get positions
all_positions = []
if body_soup.find('div', class_='resc'):
    try:
        count = 0
        for div in body_soup.find_all('div', class_='pos'):
            txt = div.get_text(strip=True).replace("mm","")
            txt = txt.replace("°","")
            txt = txt.replace(" ","")
            txt = txt.split(',')
            pos = {}
            for param in txt:
                if '=' in param:
                    param = param.split("=", 1)
                    key = param[0]
                    value = param[1]
                    try:
                        value = float(value)
                    except:
                        value = 0.0
                    pos[key] = value
            all_positions.append( { 'name':f"Position {count+1}", 'pos':pos} )
            count += 1
    except AttributeError as e:
        st.info(f"possibly missing Resource Information?")

all_positions_txt = [ f"{pos['name']}" for pos in all_positions ]

col_pos, col_postxt = st.columns(2)
with col_pos:
    position = st.selectbox("Position:", all_positions_txt, key="position")
    st.session_state["selected_mess"]["pos"] = position
with col_postxt:
    idx = get_index(all_positions_txt, st.session_state["selected_mess"]["pos"])
    st.markdown("<div style='height:32px;'></div>", unsafe_allow_html=True)
    if idx!=-1:
        pos = f'x={all_positions[idx]["pos"]["x"]}, y={all_positions[idx]["pos"]["y"]}, z={all_positions[idx]["pos"]["z"]}'
        st.markdown(f"{pos}")
        

# conditions = [ ("temp0", "298 K"), ("gases", "..."), ... ]
valid_condition_typs = ['gases','ramp','temp','dura']
if st.session_state["mess_index"]!=-1:
    for i in range(0, len(st.session_state['selected_mess']['conditions'])):
        cond_typ = st.session_state["selected_mess"]["conditions"][i][0]
        if cond_typ not in valid_condition_typs:
            continue
        col_cond, col_del = st.columns([11,1])
        with col_cond:
            ## get input class
            if cond_typ == "gases":
                cond = GasComposer(key=f"{i}")
            elif cond_typ == "ramp":
                cond = HeatingRamp(key=f"{i}")
            elif cond_typ == "comment":
                cond = RetractableComment(key=f"{i}")
            elif cond_typ == "temp":
                cond = PhysicalQuantityInput(key=f"{i}", label="Const. Temperature:", units="K")
            elif cond_typ == "temp_p":
                cond = PhysicalQuantityInput(key=f"{i}", label="Plate Temperature:", units="K")
            elif cond_typ == "dura":
                cond = DurationCondition(key=f"{i}")
            else:
                cond = None
            ## update treatment condition
            if (cond!=None):
                if (cond.key not in st.session_state["cond_input_keys"]):
                    cond.set_data(st.session_state["selected_mess"]["conditions"][i][1])
                    st.session_state["cond_input_keys"].append(cond.key)
                cond.render()
                st.session_state["selected_mess"]["conditions"][i][1] = cond.get_data()
        with col_del:
            if st.button("❌", key=f"del_cond_{i}"):
                del st.session_state["selected_mess"]["conditions"][i]
                st.rerun()

## add a new optional condition
st.markdown("---")
optional_cond = [ "Set Gas", "Duration", "Const. Temperature", "Plate Temperature", "Heating Ramp", "Comment", "Position"]

new_cond_typ = -1
col_cond_sel, col_cond_yes = st.columns([3,2])
with col_cond_sel:
    new_cond_typ = get_index(cond_names,st.selectbox('Select Condition to Add:', optional_cond, index=0, key="sel_cond"))
with col_cond_yes:
    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    if st.button("➕ Add Condition", key="new_cond"):
        if (st.session_state['mess_index']!=-1)and(new_cond_typ in range(0, len(cond_classes))):
            cond_class = cond_classes[new_cond_typ]
            if cond_class=="temp":
                new_cond = [cond_class, 0.0]
            elif cond_class=="temp_p":
                new_cond = [cond_class, 0.0]
            elif cond_class=="gases":
                new_cond = [cond_class, {} ]
            elif cond_class=="ramp":
                new_cond = [cond_class, { 'typ':0, 'start':0.0, 'stop':0.0, 'step':0.0 } ]
            elif cond_class=="dura":
                new_cond = [cond_class, ""]
            elif cond_class=="comment":
                new_cond = [cond_class, ""]
            else:
                new_cond = None
            if new_cond !=None:
                st.session_state["selected_mess"]["conditions"].append(new_cond)
                st.rerun()
            
#### Update Step ####
st.markdown("---")
if st.button("Update Treatment step", key="submit"):
    if selected_index!=-1:
        print("UPDATE!!!!!!")
        update_exp_step(exp_client, body_soup, st.session_state["selected_mess"])
        st.rerun()

    
