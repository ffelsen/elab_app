## Elab Logger

A Streamlit based app to perform simple API action for ELabFTW. The scope of this app is to provide a simple to use chat like interface
which automatically creates structured and understandable experiment and entries. All functionalities are based on Streamlit and elabapi_python.

# Setup and Usage
In order to run the app you will need a few packages. Create a python environment based on the requirement.txt. 
Next you need to provide the web address of the ElabFTW instance you want to interact with. This needs to be defined in the file main.py.
Also you need to create an API key, which goes into a separate file and will be read by main.py. The file name in main.py needs to adjusted
accordingly (here it is digi.key). 

You can run the app using the command
```
streamlit run main.py
```

# Implemented features
* creating new experiments
* adding comments to experiments in chat and template mode
* adding sketches to experiments

# To Do
* link experiment entries to data directories (e.g. on the NAS)
* track file changes in the data directory and post them to the experiment
* voice to text model for voice input of comments

