"""Shared helpers used by pages/templates.py and templates/*.py.

Kept here to avoid circular imports between the two locations.
"""
import streamlit as st
from utils import append_to_experiment


def reset():
    st.session_state.selection = 'Choose a template'


def _f(val, fmt=None):
    """Return *val* (optionally formatted with *fmt*), or '__' if empty/None."""
    if val is None:
        return '__'
    if isinstance(val, str) and not val.strip():
        return '__'
    if fmt is not None:
        return format(val, fmt)
    return str(val) if not isinstance(val, str) else val


def _append(prompt: str):
    """Write *prompt* to the currently selected elabFTW entry."""
    entity_type = st.session_state.get('entity_type', 'experiments')
    ok = append_to_experiment(
        st.session_state.api_client,
        st.session_state.exp_id,
        prompt,
        entity_type=entity_type,
        initials=st.session_state.get('initials', ''),
    )
    if ok:
        entry_label = 'experiment' if entity_type == 'experiments' else 'resource'
        message = "Wrote in %s %s: %s" % (entry_label, st.session_state.exp_name, prompt[:80])
        if "chat_history" not in st.session_state:
            st.session_state["chat_history"] = []
        st.session_state["chat_history"].append(message)
        if len(st.session_state["chat_history"]) > 10:
            st.session_state["chat_history"] = st.session_state["chat_history"][-10:]
    else:
        st.error("⚠️ Could not send to elabFTW — see **Session History** on the Add text logs page.")
