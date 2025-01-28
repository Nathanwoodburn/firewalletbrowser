import json
import account
import requests
import os

# Plugin Data
info = {
    "name": "Custom Plugin Manager",
    "description": "Import custom plugins from git repositories",
    "version": "1.0",
    "author": "Nathan.Woodburn/"
}

# Functions
functions = {
    "add":{
        "name": "Add Plugin repo",
        "type": "default",
        "description": "Add a plugin repo",
        "params": {
            "url": {
                "name":"URL",
                "type":"text"
            }
        },
        "returns": {
            "status": 
            {
                "name": "Status of the function",
                "type": "text"
            }
        }
    },
    "remove":{
        "name": "Remove Plugins",
        "type": "default",
        "description": "Remove a plugin repo from the list",
        "params": {
            "url": {
                "name":"URL",
                "type":"text"
            }
        },
        "returns": {
            "status": 
            {
                "name": "Status of the function",
                "type": "text"
            }
        }
    },
    "list":{
        "name": "List Plugins",
        "type": "default",
        "description": "List all imported plugins",
        "params": {},
        "returns": {
            "plugins": 
            {
                "name": "List of plugins",
                "type": "list"
            }
        }
    }
}

def add(params, authentication):
    url = params["url"]
    if not os.path.exists("user_data/plugins.json"):
        with open("user_data/plugins.json", "w") as f:
            json.dump([], f)

    with open("user_data/plugins.json", "r") as f:
        importurls = json.load(f)

    # Check if the plugin is already imported
    if url in importurls:
        return {"status": "Plugin already imported"}

    importurls.append(url)
    with open("user_data/plugins.json", "w") as f:
        json.dump(importurls, f)

    return {"status": "Imported"}


def remove(params, authentication):
    url = params["url"]
    if not os.path.exists("user_data/plugins.json"):
        with open("user_data/plugins.json", "w") as f:
            json.dump([], f)

    with open("user_data/plugins.json", "r") as f:
        importurls = json.load(f)

    # Check if the plugin is already imported
    if url not in importurls:
        return {"status": "Plugin not imported"}

    importurls.remove(url)
    with open("user_data/plugins.json", "w") as f:
        json.dump(importurls, f)

    return {"status": "Removed"}

def list(params, authentication):
    if not os.path.exists("user_data/plugins.json"):
        with open("user_data/plugins.json", "w") as f:
            json.dump([], f)

    with open("user_data/plugins.json", "r") as f:
        importurls = json.load(f)
    
    return {"plugins": importurls}