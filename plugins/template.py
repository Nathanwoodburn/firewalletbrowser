import json
import account
import requests

# Plugin Data
info = {
    "name": "Plugin Template",
    "description": "Plugin Description",
    "version": "1.0",
    "author": "Nathan.Woodburn/"
}

# Functions
functions = {
    "main":{
        "name": "Function name",
        "type": "dashboard",
        "description": "Description",
        "params": {},
        "returns": {
            "status": 
            {
                "name": "Status of the function",
                "type": "text"
            }
        }
    }
}

def main(params, authentication):
    return {"status": "Success"}
    