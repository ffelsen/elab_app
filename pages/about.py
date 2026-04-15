import re

import requests
import streamlit as st

from version import LOG_SCHEMA_VERSION, LOG_SCHEMA_URL

_GITHUB_URL    = LOG_SCHEMA_URL  # https://github.com/ffelsen/elab_app
_RAW_VERSION   = (
    "https://raw.githubusercontent.com/ffelsen/elab_app/main/src/elab_app/version.py"
)


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_remote_version() -> str | None:
    """Return LOG_SCHEMA_VERSION from the remote version.py, or None on failure."""
    resp = requests.get(_RAW_VERSION, timeout=8)
    resp.raise_for_status()
    m = re.search(r'^LOG_SCHEMA_VERSION\s*=\s*"([^"]+)"', resp.text, re.MULTILINE)
    return m.group(1) if m else None


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse 'v3.1' → (3, 1). Returns (0,) on failure."""
    m = re.match(r'^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?', v.strip())
    if not m:
        return (0,)
    return tuple(int(x) for x in m.groups() if x is not None)


# ── Page ──────────────────────────────────────────────────────────────────────

st.title("About elab-app")

# ── Installed version ─────────────────────────────────────────────────────────
st.subheader("Installed version")
st.metric("Version", LOG_SCHEMA_VERSION)

# ── Remote version check ──────────────────────────────────────────────────────
st.subheader("Latest version on GitHub")

with st.spinner("Checking GitHub for updates…"):
    try:
        remote = _fetch_remote_version()
        if remote is None:
            st.warning("⚠️ Could not parse the version from the remote repository.")
        elif remote == LOG_SCHEMA_VERSION:
            st.success(f"✅ You are up to date ({LOG_SCHEMA_VERSION}).")
        elif _parse_version(LOG_SCHEMA_VERSION) > _parse_version(remote):
            st.info(
                f"ℹ️ You are running a development version **{LOG_SCHEMA_VERSION}** "
                f"ahead of the latest published release ({remote})."
            )
        else:
            st.warning(
                f"⬆️ A newer version is available: **{remote}**  \n"
                f"You have **{LOG_SCHEMA_VERSION}**. See the update instructions below."
            )
    except Exception as exc:
        st.error(
            f"⚠️ Could not reach the GitHub repository.  \n"
            f"`{exc}`  \n\n"
            "The repository URL may have changed or been moved. "
            "Please **contact your elabFTW admin** to obtain the current install command."
        )

# ── Links ─────────────────────────────────────────────────────────────────────
st.subheader("Repository")
st.markdown(f"[{_GITHUB_URL}]({_GITHUB_URL})")

# ── Update instructions ───────────────────────────────────────────────────────
st.subheader("How to update")
st.markdown(
    "Run the following command in your terminal. "
    "It reinstalls from the latest commit on GitHub:"
)
st.code(f"uv tool install --reinstall git+{_GITHUB_URL}", language="bash")
st.markdown(
    "If you need **voice transcription** (requires a capable machine — "
    "downloads several GB of ML models on first use):"
)
st.code(f'uv tool install --reinstall "git+{_GITHUB_URL}[transcription]"', language="bash")
