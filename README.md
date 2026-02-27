## Elab Logger

A Streamlit-based app to perform simple API actions for elabFTW. The scope of this app is to provide a simple, chat-like interface which automatically creates structured and understandable experiment entries. All functionality is built on Streamlit and `elabapi_python`.

---

# Setup

## 1. Dependencies

The repository is managed with [uv](https://docs.astral.sh/uv/). Install it on macOS/Linux with:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

or on Windows with:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Make sure streamlit is installed as a tool:

```bash
uv tool install streamlit
```

## 2. Host address

The elabFTW instance URL is set in `auth.py`:

```python
ELAB_HOST = "https://your-elab-instance.example.com/api/v2"
```

Update this constant once for your deployment — it applies to all users.

## 3. User accounts & API keys

Each user sets up their own encrypted credential on first use, directly inside the app (see **First-time login** below). No manual file editing is required.

Encrypted key files are stored locally in `keys/<short_name>.enc` and are excluded from version control via `.gitignore`. They provide basic safety on a shared machine because the API key is only decrypted in memory, and only after the correct PIN is entered.

---

# Running the app
Run the app from the main depository folder including main.py by using uv and the streamlit tool installed.

```bash
uv run -- streamlit run main.py
```

---

# First-time login (new user setup)

When no key file exists for a user, the app shows a setup dialog:

1. **Short name** — choose a short, lowercase identifier (e.g. `alice`). This becomes the filename `keys/alice.enc`. The dropdown will list any existing users on the machine.
2. **PIN** — a short passphrase that protects the encrypted file. You will type this every time you open the app.
3. **elabFTW API key** — paste your personal API key (find it in elabFTW under **User Panel → API KEYS**). You only ever enter this once; after setup it is stored encrypted and never shown again.
4. Click **Set up** — the app verifies the API key against elabFTW, saves the encrypted file, and confirms: *"You will write into elabFTW as [elabFTW first and last name]"*

To reset your account, simply delete `keys/<short_name>.enc` and go through setup again.

# Subsequent logins

Select your short name from the dropdown, enter your PIN, and click **Log in**. Your display name and team are fetched automatically from elabFTW — no manual name entry needed.

---

# Implemented features

* Encrypted per-user API key store (PIN-protected, Fernet/PBKDF2)
* Automatic display-name and team lookup via `GET /users/me`
* Creating new experiments
* Adding comments to experiments in chat and template mode
* Adding sketches to experiments
* Transcribing spoken content with timestamps

# To Do

* Single sign-on (e.g. Shibboleth)
* Team switching within the app session
* Connecting to data (e.g. on a NAS or data tagger)
