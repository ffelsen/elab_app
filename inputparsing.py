#!/usr/bin/python
import streamlit as st

####### GLOBAL CONSTANTS ########
DAY_MICROS = 24*60*60*1000*1000
HOUR_MICROS = 60*60*1000*1000
MIN_MICROS = 60*1000*1000
SEC_MICROS = 1000*1000

####### GENERAL FUNCTIONS ########
def abbrv_s(s):
    return s[:4] + "." if len(s) > 5 else s
    
def get_index(lst, elm, dflt=-1):
    try:
        return lst.index(elm)
    except ValueError:
        return dflt

#### parsing and formating ####
def t_time_str(t_time):
    out = ""
    for s_unit in t_time:
        if t_time[s_unit] > 0: out += f"{int(t_time[s_unit])} {s_unit}, ";
    if len(out)>2: out = out[:-2];
    out = out.replace('u','µ')
    if out =="":
        return "0 µs"
    else:
        return out
    
def convert_time_units(numb,s_unit,t_time):
    convert_micros = { "d":DAY_MICROS, "h":HOUR_MICROS, "min":MIN_MICROS, "s":SEC_MICROS, "ms":1000, "us":1}
    s_units = s_unit.replace('µ','u')
    if s_units in convert_micros:
        dt_micros = numb*convert_micros[s_units]
        for key in convert_micros:
            dt_i = dt_micros//convert_micros[key]
            t_time[key] += dt_i
            dt_micros -= dt_i*convert_micros[key]
    return t_time
    
def parse_duration(s):
    t_time = { "d":0, "h":0, "min":0, "s":0, "ms":0, "us":0 }
    s_numb = ""
    s_unit = "d"
    NUMB, UNIT = ( 0, 1 )
    mode = UNIT
    flt_pnt = False
    for c in s:
        if (ord(c)>=ord('0'))and(ord(c)<=ord('9')):
            if mode==UNIT:
                try: numb = float(s_numb);
                except ValueError: numb = 0.;
                t_time = convert_time_units(numb,s_unit,t_time)
                s_numb = "";
                flt_pnt = False
            mode = NUMB
            s_numb += c
        elif (c=='.')and(not flt_pnt):
            if mode==UNIT:
                try: numb = float(s_numb);
                except ValueError: numb = 0.;
                t_time = convert_time_units(numb,s_unit,t_time)
                s_numb = "";
            s_numb += c
            flt_pnt = True
        elif ((ord(c)>=ord('a'))and(ord(c)<=ord('z')))or(c=='µ'):
            if mode==NUMB:
                s_unit = ""
            mode = UNIT
            s_unit += c
    if mode==NUMB:
        pass
    elif mode==UNIT:
        try: numb = float(s_numb);
        except ValueError: numb = 0.;
        t_time = convert_time_units(numb,s_unit,t_time)
    return t_time

#### get user input ####
def duration_text_input(key, label, default="0 min", label_visibility="visible", on_change=None):
    if key not in st.session_state:
        st.session_state[key] = default
    user_input = st.text_input(label, value=st.session_state[key], label_visibility=label_visibility, key=key + "_input",on_change=on_change)
    st.session_state[key] = t_time_str(parse_duration(user_input))
    return st.session_state[key]
    
def float_text_input(key, label, default="0.0", label_visibility="visible", on_change=None):
    if key not in st.session_state:
        st.session_state[key] = default
    user_input = st.text_input(label, value=st.session_state[key], label_visibility=label_visibility, key=key + "_input", on_change=on_change)
    try:
        val = float(user_input)
        st.session_state[key] = user_input
        return val
    except ValueError:
        return default

#### Classes ####
class GasComposer:
    def __init__(self, key, options_gases=None):
        self.key = f"gas_parts_{key}"
        self.options_gases = options_gases or ["Ar", "CO", "H2", "He", "N2", "O2"]
        if self.key not in st.session_state:
            st.session_state[self.key] = {}
    
    def on_change(self):
        pass
            
    def render(self):
        composition_line = []
        for gas in st.session_state[self.key]:
            composition_line.append(f"{gas} ({st.session_state[self.key][gas]} mbar)")
        if len(st.session_state[self.key])==0:
            composition_line = "UHV"
        else:
            composition_line = f"{', '.join(composition_line)}"
        
        with st.expander(f"Set Gas Composition:\u00A0 \u00A0 {composition_line} (old)", expanded=True):
            col_gas, col_pre, col_del, col_add = st.columns([4,5,3,3])
            with col_gas:
                current_gas = st.selectbox("Select Gas", self.options_gases, key=self.key+"_gas")
            with col_pre:
                current_pre = float_text_input(self.key+"_pre", "part. Pressure [mbar]", default="0.0")
            with col_del:
                st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                if st.button("❌ Delete", key=f"del_{self.key}"):
                    st.session_state[self.key].pop(current_gas, None)
                    st.rerun()
            with col_add:
                st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                if st.button("➕ Add", key=f"add_{self.key}"):
                    if current_pre>0:
                        st.session_state[self.key][current_gas] = current_pre
                        st.rerun()
                        
            composition_line = []
            for gas in st.session_state[self.key]:
                composition_line.append(f"{gas} ({st.session_state[self.key][gas]} mbar)")
            if len(st.session_state[self.key])==0:
                composition_line = "UHV"
            else:
                composition_line = f"{', '.join(composition_line)}"
            
            st.markdown(f"**Gas Composition**:\u00A0 \u00A0 {composition_line}")
            
    def set_data(self, data):
        st.session_state[self.key] = data
        
    def get_data(self):
        return st.session_state[self.key]

class HeatingRamp:
    def __init__(self, key, typ="pow"):
        self.key = f"heat_ramp_{key}"
        self.options_typ = ["Power", "Temperature"]
        self.all_units = ["W", "K"]
        typ = typ.strip().lower()
        if typ.startswith("pow"):
            typi = 0
        elif typ.startswith("temp"):
            typi = 1
        else:
            typi = 0
        
        default_state = { 
            "typ":typi, 
            "start":0.0, 
            "stop":0.0, 
            "step":0.0, 
        }
        st.session_state.setdefault(self.key, default_state.copy())
    
    def on_change(self):
        pass
            
    def render(self):
        typi = st.session_state[self.key]['typ']
        start = st.session_state[self.key]['start']
        stop = st.session_state[self.key]['stop']
        step = st.session_state[self.key]['step']
        #expanded = st.session_state[self.key]["expanded"]
        
        typ = self.options_typ[typi]
        units = self.all_units[typi]
        
        old_typi = typi
        old_ramp_line = f"{start} {units} ➔ {stop} {units};\u00A0 @ {step} {units}/step"
        
        with st.expander(f"{typ} Ramp:\u00A0 \u00A0 {old_ramp_line} (old)",expanded=True):
            col_typ, col_start, col_stop, col_step = st.columns([2,1,1,1])
            with col_typ:
                typ = st.selectbox("Typ:", self.options_typ, key=self.key+"_typ", on_change=self.on_change)
                typi = get_index(self.options_typ, typ)
                st.session_state[self.key]['typ'] = typi
            with col_start:
                start = float_text_input(self.key+"_start", "Start:", default="0.0")
                st.session_state[self.key]['start'] = start
            with col_stop:
                stop = float_text_input(self.key+"_stop", "Stop:", default="0.0")
                st.session_state[self.key]['stop'] = stop
            with col_step:
                step = float_text_input(self.key+"_step", "Step:", default="0.0")
                st.session_state[self.key]['step'] = step
            
            ramp_line = f"{start} {units} ➔ {stop} {units};\u00A0 @ {step} {units}/step"
            st.markdown(f"**{typ} Ramp:**\u00A0 \u00A0 {ramp_line}")
                
    def set_data(self, data):
        st.session_state[self.key] = data
        st.session_state[self.key+"_typ"] = self.options_typ[data["typ"]]
        st.session_state[self.key+"_start"] = data["start"]
        st.session_state[self.key+"_stop"] = data["stop"]
        st.session_state[self.key+"_step"] = data["step"]
        print("DATA:",data["typ"],data["start"],data["stop"],data["step"])
        
    def get_data(self):
        return st.session_state[self.key]
        
class RetractableComment:
    def __init__(self, key, label="Comment:"):
        self.key = f"comment_{key}"
        self.label = label
        if self.key not in st.session_state:
            st.session_state[self.key] = ""
            
    def render(self):
        with st.expander(f"{self.label} (old)",expanded=True):
            st.session_state[self.key] = st.text_area(self.label, label_visibility="collapsed", value=st.session_state[self.key], height=None, max_chars=None, key=self.key+"_com")

    def set_data(self, data):
        st.session_state[self.key] = data
        
    def get_data(self):
        return st.session_state[self.key]
        
class PhysicalQuantityInput:
    def __init__(self, key, label="Physical Quantity:", units="a.u."):
        self.key = f"comment_{key}"
        self.label = label
        self.units = units
        if self.key not in st.session_state:
            st.session_state[self.key] = 0.0
    
    def on_change(self):
        pass
            
    def render(self):
        old_value = st.session_state[self.key]
        with st.expander(f"{self.label}\u00A0 \u00A0 {old_value} {self.units} (old)",expanded=True):
            st.session_state[self.key] = float_text_input(self.key+"_phy", self.label, label_visibility="collapsed", default="0.0")
            if old_value!=st.session_state[self.key]:
                st.session_state[self.key+"_phy"] = st.session_state[self.key]
                
    def set_data(self, data):
        st.session_state[self.key] = data
        st.session_state[self.key+"_phy"] = data
        
    def get_data(self):
        return st.session_state[self.key]

class IonEnergyCondition:
    def __init__(self, key, label="Ion Energy:"):
        self.key = f"comment_{key}"
        self.label = label
        if self.key not in st.session_state:
            st.session_state[self.key] = { 'U':0.0, 'I':0.0 }
        
    def on_change(self):
        pass
            
    def render(self):
        U = st.session_state[self.key]["U"]
        I = st.session_state[self.key]["I"]
        old_line = f"{U} V ({I} mA)"
        with st.expander(f"{self.label}\u00A0 \u00A0 {old_line} (old)",expanded=True):
            col_U, col_I = st.columns(2)
            with col_U:
                U = float_text_input(self.key+"_vol", "Voltage [V]", default="0.0")
                st.session_state[self.key]["U"] = U
            with col_I:
                I = float_text_input(self.key+"_cur", "Current [mA]", default="0.0")
                st.session_state[self.key]["I"] = I
            new_line = f"{I} V ({I} mA)"
            if old_line!=new_line:
                st.session_state[self.key+"_vol"] = st.session_state[self.key]["U"]
                st.session_state[self.key+"_cur"] = st.session_state[self.key]["I"]
                old_line = new_line
                
    def set_data(self, data):
        st.session_state[self.key] = data
        st.session_state[self.key+"_vol"] = data["U"]
        st.session_state[self.key+"_cur"] = data["I"]
        
    def get_data(self):
        return st.session_state[self.key]
        
class DurationCondition:
    def __init__(self, key, label="Duration:"):
        self.key = f"dura_{key}"
        self.label = label
        if self.key not in st.session_state:
            st.session_state[self.key] = ""
            
    def on_change(self):
        pass

    def render(self):
        old_value = st.session_state[self.key]
        with st.expander(f"{self.label}\u00A0 \u00A0 {old_value} (old)",expanded=True):
            st.session_state[self.key] = duration_text_input(self.key+"_dura", self.label, label_visibility="collapsed", default="0.0", on_change=self.on_change)
            if old_value!=st.session_state[self.key]:
                st.session_state[self.key+"_dura"] = st.session_state[self.key]
                
    def set_data(self, data):
        st.session_state[self.key] = data
        st.session_state[self.key+"_dura"] = data
        
    def get_data(self):
        return st.session_state[self.key]


