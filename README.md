## Elab Logger

A Streamlit-based app to perform simple API actions for elabFTW. The scope of this app is to provide a simple, chat-like interface which automatically creates structured and understandable experiment entries. All functionality is built on Streamlit and `elabapi_python`.

---

# Setup

## 1. Install

Install [uv](https://docs.astral.sh/uv/) on macOS/Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

or on Windows:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then install the app as a uv tool:

```bash
uv tool install git+https://github.com/ffelsen/elab_app
```

To include voice transcription (requires a capable machine — downloads several GB of ML models on first use):

```bash
uv tool install "git+https://github.com/ffelsen/elab_app[transcription]"
```

## 2. Host address

Set the elabFTW API URL once with:

```bash
elab-app config set elab_host https://your-elab-instance.example.com/api/v2
```

This is stored in the OS-standard config directory (e.g. `~/.config/elab_app/config.toml` on Linux/macOS). Run `elab-app config show` to see the current value.

## 3. User accounts & API keys

Each user sets up their own encrypted credential on first use, directly inside the app (see **First-time login** below). No manual file editing is required.

Encrypted key files are stored in `~/.config/elab_app/keys/<initials>.enc`. The API key is only decrypted in memory after the correct PIN is entered — it is never stored in plaintext.

> **Tip — reusing an existing key on a new machine:** Copy `~/.config/elab_app/keys/<initials>.enc` from the old machine to the same path on the new one. No new API key is needed.

> **Upgrading from the old layout (repo-local `keys/`):** Copy your `.enc` files from the repo's `keys/` folder to `~/.config/elab_app/keys/`.

## 4. Templates

YAML templates are stored in `~/.config/elab_app/templates/`. The first time you run `elab-app start`, the package's built-in example templates are copied there automatically. Edit or add `.yaml` files in that folder to customise them; the app reloads them on each page visit.

---

# Updating

To update to the latest version, run:

```bash
uv tool install --reinstall git+https://github.com/ffelsen/elab_app
```

Or, if you installed with voice transcription:

```bash
uv tool install --reinstall "git+https://github.com/ffelsen/elab_app[transcription]"
```

The **About** page (accessible from the app's navigation) shows your installed version and automatically checks GitHub for a newer release.

---

# Running the app

```bash
elab-app start
```

This opens the Streamlit interface in your browser. The command can be run from any directory.

For development (running directly from the repo):

```bash
uv run -- streamlit run src/elab_app/main.py
```

---

# First-time login (new user setup)

When no key file exists for a user, the app shows a setup dialog:

1. **Initials** — choose your initials in lowercase (e.g. `ljf`). This becomes the filename `~/.config/elab_app/keys/ljf.enc`. The dropdown will list any existing users on the machine.
2. **PIN** — a short passphrase that protects the encrypted file. You will type this every time you open the app.
3. **elabFTW API key** — paste your personal API key (find it in elabFTW under **User Panel → API KEYS**). You only ever enter this once; after setup it is stored encrypted and never shown again.
4. Click **Set up** (or press Enter) — the app verifies the API key against elabFTW, saves the encrypted file, confirms *"You will write into elabFTW as [elabFTW first and last name]"*, and logs you in automatically.

To reset your account, delete `~/.config/elab_app/keys/<initials>.enc` and go through setup again.

# Subsequent logins

Select your initials from the dropdown, enter your PIN, and press Enter or click **Log in**. Your display name and team are fetched automatically from elabFTW — no manual name entry needed.

---

# Adding and editing templates

Templates appear in the **Add comment → Template mode** dropdown. Two kinds coexist:

## YAML templates (recommended for most cases)

Create a `.yaml` file in the `templates/` folder — the app picks it up automatically on next start, no code changes needed. Use `templates/example_all_options.yaml` as your starting point; it documents every available field type with inline comments.

Available field types:

| `type` | Widget | Extra keys |
|--------|--------|------------|
| `number` | Numeric spinner | `units: [K, °C, ...]` — adds a unit selector |
| `sci_number` | Free-text input | `units: [...]` — accepts `3e-10`, `1.5E-4`, etc. |
| `select` | Dropdown | `options: [A, B, C]` — required |
| `text` | Single-line input | `placeholder:` — optional hint text |
| `textarea` | Multi-line input | `placeholder:` — optional hint text |

In the `output:` string, write `{Label}` to insert a field value. For `number` and `sci_number` fields with units, the chosen unit is appended automatically (e.g. `{Temperature}` → `42.000 K`).

YAML template files are **not synced with git** (excluded via `.gitignore`). Only `example_all_options.yaml` is tracked as a reference. This means each machine/user maintains their own set of templates.

## Python templates (for complex logic)

For templates that need conditional fields (e.g. spot size depending on excitation energy), add a `@st.dialog`-decorated function to `pages/templates.py`. Any function whose name contains `"template"` is discovered automatically.

---

# Log table format (v3.1)

Each elab-app log is stored as an HTML table inside the elabFTW entry body. The format has been stable since v2.x with one addition in v3.0: a per-row **App version** column.

| Column | Content |
|--------|---------|
| ISO time (ISO 8601) | Timestamp of the log entry |
| Log (newest to oldest) | Free-text content (supports Markdown → HTML) |
| Initials | User initials (lowercase, max 6 chars) |
| App version | Version of elab_app that wrote the row (e.g. `v3.1`); rows migrated from v2.x show `2.x` |

- The first row of every table is an identifier row (`elab_app | repo URL | | `) used for detection.
- The app merges all log tables it finds in an entry into one on the next write — multiple tables are consolidated automatically regardless of which app version created them.
- Legacy rows (3 columns, written before v3.0) are back-filled with `2.x` in the App version column when read.

### Auto-linking

When a log entry references an elabFTW resource or experiment using an internal link (e.g. via the `#` hashtag autocomplete), the app automatically creates the corresponding database-level link (visible under **Linked items** / **Linked experiments** in elabFTW), mirroring what the built-in editor does.

---

# Implemented features

* Encrypted per-user API key store (PIN-protected, Fernet/PBKDF2)
* Automatic display-name and team lookup via `GET /users/me`
* Team selection at login (with per-team experiment categories and access rights)
* Creating new experiments and resources
* Adding comments in chat and template mode
* YAML-based user-defined templates (no coding required)
* Adding sketches to entries
* Voice transcription with optional per-segment timestamps (Whisper-based, optional install)
* Download log entries filtered by date range as a zip of JSON files
* Per-row app version tracking in the log table
* Auto-linking of referenced resources/experiments as elabFTW database links
* API error handling with failed-entry history, red highlighting, and re-send button
* About page with version check against the GitHub repository

# To Do

* Single sign-on (e.g. Shibboleth)
* Team switching within the app session
* Connecting to data (e.g. on a NAS or data tagger)
