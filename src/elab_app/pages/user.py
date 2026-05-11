import streamlit as st

st.header("User")

fullname = st.session_state.get("fullname", "—")
initials = st.session_state.get("initials", "—")
team     = st.session_state.get("team",     "—")
teams    = st.session_state.get("teams",    [])

st.write(f"**Name:** {fullname}")
st.write(f"**Initials (key file):** `{initials}`")
st.write(f"**Team:** {team}")

if len(teams) > 1:
    other = [t["name"] for t in teams if t["name"] != team]
    st.caption(
        f"Also a member of: {', '.join(other)}. "
        "Start a new session to switch teams."
    )

st.divider()

if st.button("Log out", type="primary"):
    st.session_state.clear()
    st.rerun()
