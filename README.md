## Elab Logger

A Streamlit based app to perform simple API action for ELabFTW. The scope of this app is to provide a simple to use chat like interface
which automatically creates structured and understandable experiment and entries. All functionalities are based on Streamlit and elabapi_python.

# Setup 
You need to provide the host address of the ElabFTW instance you want to interact with in the main.py under "configuration.host".
Identification currently works via an API key, which goes into a separate file named digi.key and will be read by main.py.

# Usage
The depository is managed with uv, which you can install on MacOS and Linux with
```
curl -LsSf https://astral.sh/uv/install.sh | sh
````
and on Windows with 
```
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
Please make sure user has access to uv and elab directories.
For more information visit Astral's uv documentation pages.

Then install streamlit as a uv tool with
```
uv tool install streamlit
```
Then you can run the app from the depository directory using the command
```
uv run -- streamlit run main.py
```

# Implemented features
* creating new experiments
* adding comments to experiments in chat and template mode
* adding sketches to experiments
* transcribing spoken content with timestamps

# To Do
* single sign on (ie Shibolet)
* connecting to data (e.g. on a NAS or data tagger)


