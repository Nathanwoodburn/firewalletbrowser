import json
import account
import requests

# Plugin Data
info = {
    "name": "Public Node Dashboard",
    "description": "Dashboard modules for public nodes",
    "version": "1.0",
    "author": "Nathan.Woodburn/"
}

# Functions
functions = {
    "main":{
        "name": "Info Dashboard widget",
        "type": "dashboard",
        "description": "This creates the widget that shows on the dashboard",
        "params": {},
        "returns": {
            "status": 
            {
                "name": "Status of Node",
                "type": "text"
            }
        }
    }
}

def main(params, authentication):
    info = account.hsd.getInfo()

    status = f"Version: {info['version']}<br>Inbound Connections: {info['pool']['inbound']}<br>Outbound Connections: {info['pool']['outbound']}<br>"
    if info['pool']['public']['listen']:
        status += f"Public Node: Yes<br>Host: {info['pool']['public']['host']}<br>Port: {info['pool']['public']['port']}<br>"
    else:
        status += f"Public Node: No<br>"
    status += f"Agent: {info['pool']['agent']}<br>Services: {info['pool']['services']}<br>"

    return {"status": status}
    