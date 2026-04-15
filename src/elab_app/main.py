from pathlib import Path

import streamlit as st
from warnings import filterwarnings

from auth import (
    is_valid_short_name,
    list_users,
    user_exists,
    save_key,
    load_key,
    fetch_user_info,
    build_api_client_from_session,
)

filterwarnings("ignore")

_HERE = Path(__file__).parent
st.logo(str(_HERE / "content" / "logo.png"), size="large")

st.set_page_config(page_title="ElabFTW Logger")

# ── Login / setup dialog ──────────────────────────────────────────────────────

@st.dialog("Sign in to ElabFTW Logger")
def login_dialog():
    """Unified login + first-time setup dialog."""

    known_users = list_users()
    dropdown_options = known_users + ["+ New user"]

    # ── Initials selector ────────────────────────────────────────────────────
    selected = st.selectbox(
        "Initials",
        options=dropdown_options,
        index=len(dropdown_options) - 1,  # default: "+ New user"
        key="_login_dropdown",
    )

    if selected == "+ New user":
        short_name = st.text_input(
            "Choose your initials",
            placeholder="e.g. ljf",
            key="_login_shortname_input",
        )
    else:
        short_name = selected
        st.text_input(
            "Initials",
            value=short_name,
            disabled=True,
            key="_login_shortname_display",
        )

    # ── Live initials feedback ───────────────────────────────────────────────
    is_new = selected == "+ New user"

    if short_name:
        if not is_valid_short_name(short_name):
            st.markdown(
                ':red[Initials not valid — only use lowercase letters, '
                'digits, and underscores (must start with a letter, max 6 characters).]'
            )
            name_ok = False
        elif is_new and user_exists(short_name):
            st.markdown(
                f':orange[Initials **{short_name}** already have a key file. '
                'Select them from the dropdown to log in, or choose different initials.]'
            )
            name_ok = False
        elif not is_new:
            st.markdown(':green[Known user — please enter your PIN.]')
            name_ok = True
        else:
            st.markdown(f':green[New user **{short_name}** — fill in your PIN and API key below.]')
            name_ok = True
    else:
        name_ok = False

    # ── PIN + submit (form so Enter key works) ──────────────────────────────
    with st.form("_login_form"):
        pin = st.text_input("PIN", type="password", key="_login_pin",
                            help="A short passphrase you'll type each time you open the app.")
        if is_new:
            api_key_input = st.text_input(
                "elabFTW API key",
                type="password",
                key="_login_apikey",
                help="Find your API key in elabFTW under **Profile → API Keys**.",
            )
            st.caption(
                "ℹ️ You only enter this once. After setup it is stored encrypted "
                "and never shown again."
            )
        else:
            api_key_input = ""

        st.divider()
        col1, _ = st.columns(2)
        submitted = col1.form_submit_button(
            "Set up" if is_new else "Log in",
            use_container_width=True,
            type="primary",
        )

    login_clicked = submitted and not is_new
    setup_clicked = submitted and is_new

    # ── Log-in flow ──────────────────────────────────────────────────────────
    if login_clicked:
        if not short_name or not pin:
            st.error("Please enter your initials and PIN.")
        elif not name_ok:
            st.error("Please fix the initials first.")
        else:
            try:
                api_key = load_key(short_name, pin)
            except FileNotFoundError:
                st.error(f"No key file found for '{short_name}'. "
                         "Please set up a new account.")
                st.stop()
            except ValueError:
                st.error("Incorrect PIN — please try again.")
                st.stop()

            # Fetch display name & teams from elabFTW
            try:
                info = fetch_user_info(api_key)
            except Exception as e:
                st.error(f"Could not connect to elabFTW: {e}")
                st.stop()

            # Route to team selection if the user belongs to more than one team.
            # Dialogs cannot be nested, so we stage the credentials in session
            # state and rerun — the main script will open team_dialog next cycle.
            if len(info["teams"]) > 1:
                st.session_state["_pending_login"] = {"api_key": api_key, "info": info, "short_name": short_name}
                st.rerun()
            else:
                team = info["teams"][0] if info["teams"] else {"id": 0, "name": ""}
                _complete_login(api_key, info, team, short_name)

    # ── Set-up flow ──────────────────────────────────────────────────────────
    if setup_clicked:
        errors = []
        if not name_ok or not short_name:
            errors.append("Please provide valid initials.")
        if not pin:
            errors.append("Please enter a PIN.")
        if not api_key_input:
            errors.append("Please enter your elabFTW API key.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            # Verify the API key works and fetch user info
            try:
                info = fetch_user_info(api_key_input)
            except Exception as e:
                st.error(f"Could not connect to elabFTW with that API key: {e}")
                st.stop()

            # Save the encrypted key file
            try:
                save_key(short_name, pin, api_key_input)
            except Exception as e:
                st.error(f"Could not save key file: {e}")
                st.stop()

            st.success(
                f"Set up! You will write into elabFTW as **{info['fullname']}**. "
                "Logging you in…"
            )

            if len(info["teams"]) > 1:
                st.session_state["_pending_login"] = {"api_key": api_key_input, "info": info, "short_name": short_name}
                st.rerun()
            else:
                team = info["teams"][0] if info["teams"] else {"id": 0, "name": ""}
                _complete_login(api_key_input, info, team, short_name)


@st.dialog("Select team")
def team_dialog(api_key: str, info: dict):
    """Let the user choose which team to work in, then complete login.

    This dialog is only shown when the user belongs to more than one team.
    Team choice determines which experiment categories (and their associated
    rights) are available throughout the session.
    """
    teams = info["teams"]
    team_names = [t["name"] for t in teams]

    st.write(
        f"You are a member of **{len(teams)} teams**. "
        "Please choose which team you want to work in for this session:"
    )

    with st.form("_team_form"):
        chosen_name = st.radio(
            "Team",
            options=team_names,
            index=0,
            key="_team_radio",
        )

        st.caption(
            "ℹ️ Your choice determines which experiment categories and "
            "access rights are available. You can start a new session to switch teams."
        )

        submitted = st.form_submit_button("Continue", type="primary", use_container_width=True)

    if submitted:
        chosen = next(t for t in teams if t["name"] == chosen_name)
        short_name = st.session_state.get("_pending_login", {}).get("short_name", "")
        st.session_state.pop("_pending_login", None)
        _complete_login(api_key, info, chosen, short_name)


def _complete_login(api_key: str, info: dict, team: dict, short_name: str = ""):
    """Store all login state in session and rerun to dismiss the dialog."""
    st.session_state["api_key"] = api_key
    st.session_state["api_client"] = build_api_client_from_session(api_key)
    st.session_state["fullname"] = info["fullname"]
    st.session_state["fn"] = info["firstname"]
    st.session_state["ln"] = info["lastname"]
    st.session_state["userid"] = info["userid"]
    st.session_state["teams"] = info["teams"]
    st.session_state["team"] = team["name"]
    st.session_state["team_id"] = team["id"]
    st.session_state["initials"] = short_name
    st.session_state["prompt"] = None
    st.rerun()


# ── App entry point ───────────────────────────────────────────────────────────

if "_pending_login" in st.session_state:
    # Credentials verified but team not yet chosen — open team dialog.
    # This is a separate render cycle from login_dialog, so no nesting occurs.
    pending = st.session_state["_pending_login"]
    team_dialog(pending["api_key"], pending["info"])
    st.stop()

if "api_client" not in st.session_state:
    # Not yet logged in — show login / setup dialog.
    login_dialog()
    st.stop()

# ── Logged-in header ──────────────────────────────────────────────────────────

st.write("# Welcome to the ElabFTW log app!")
st.image(str(_HERE / "content" / "e-conversion_logo.png"))

fullname = st.session_state.get("fullname", "")
team = st.session_state.get("team", "")
exp_name = st.session_state.get("exp_name", "")
entity_type = st.session_state.get("entity_type", "experiments")
entry_label = "Experiment" if entity_type == "experiments" else "Resource"
info_text = f"Logged in as **{fullname}** · Team **{team}**"
if exp_name:
    info_text += f" · {entry_label}: **{exp_name}**"
col_info, col_btn = st.columns([5, 1])
col_info.info(info_text)
if col_btn.button("Log out", use_container_width=True):
    st.session_state.clear()
    st.rerun()

# ── Page navigation ───────────────────────────────────────────────────────────

main_page = st.Page("pages/main_page.py", title="Open")
page_3 = st.Page("pages/comment.py", title="Add text logs")
page_4 = st.Page("pages/sketch.py", title="Add sketch")
page_about = st.Page("pages/about.py", title="About")

pg = st.navigation([main_page, page_3, page_4, page_about])
pg.run()
