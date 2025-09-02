import json
import account
import requests
import os

if not os.path.exists("user_data"):
    os.mkdir("user_data")

# Plugin Data
info = {
    "name": "Varo Functions",
    "description": "Integration with Varo.",
    "version": "1.0",
    "author": "Nathan.Woodburn/"
}

# Functions
functions = {
    "status":{
        "name": "Check connection",
        "type": "dashboard",
        "description": "You need to login to the varo instance before you can use this function.",
        "params": {},
        "returns": {
            "status": 
            {
                "name": "Status of varo connection",
                "type": "text"
            }
        }
    },
    "login":{
        "name": "Login to Varo",
        "type": "default",
        "description": "Login to Varo<br>Use the domain of the varo instance (eg. <a target='_blank' href='https://domains.hns.au'>domains.hns.au</a>) and API key from the dashboard.",
        "params": {
            "instance": {
                "name":"Varo instance",
                "type":"text"
            },
            "api": {
                "name":"API key",
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
    "addDomain":{
        "name": "Add domain",
        "type": "default",
        "description": "Add a domain to Varo",
        "params": {
            "domain": {
                "name":"Domain",
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
    
    }
}

def status(params, authentication):
    # Try to connect to Varo
    if not os.path.exists("user_data/varo.json"):
        return {"status": "Missing Varo API or instance"}

    with open("user_data/varo.json", "r") as f:
        auth = json.load(f)
        if not auth:
            return {"status": "Missing Varo API or instance"}
        if 'api' not in auth or 'instance' not in auth:
            return {"status": "Missing Varo API or instance"}
        api = auth["api"]
        instance = auth["instance"]

    headers = {"Authorization": f"Bearer {api}"}
    data = {
        "action": "getInfo"
    }
    response = requests.post(f"https://{instance}/api", json=data, headers=headers)
    if response.status_code != 200:
        return {"status": "Error connecting to Varo"}
    if not response.json()["success"]:
        return {"status": "Error connecting to Varo"}
    return {"status": f"Connected to {instance}"}

def login(params, authentication):
    # Verify the user has entered the correct details
    instance = params["instance"]
    api = params["api"]

    # Strip the https:// from the instance
    instance = instance.replace("https://", "")
    instance = instance.replace("http://", "")

    response = requests.post(f"https://{instance}/api", json={"action": "getInfo"}, headers={"Authorization": f"Bearer {api}"})
    if response.status_code != 200:
        return {"status": "Error connecting to Varo"}
    
    if not response.json()["success"]:
        return {"status": "Error connecting to Varo"}
    
    auth = {
        "instance": instance,
        "api": api
    }
    # Save the API key to the varo.json file
    with open("user_data/varo.json", "w") as f:
        json.dump(auth, f)
    
    return {"status": "Success"}

def addDomain(params, authentication):
    # Add a domain to Varo
    domain = params["domain"]

    if not os.path.exists("user_data/varo.json"):
        return {"status": "Missing Varo API or instance"}

    with open("user_data/varo.json", "r") as f:
        auth = json.load(f)
        if not auth:
            return {"status": "Missing Varo API or instance"}
        if 'api' not in auth or 'instance' not in auth:
            return {"status": "Missing Varo API or instance"}
        api = auth["api"]
        instance = auth["instance"]
    
    headers = {"Authorization": f"Bearer {api}"}
    data = {
        "action": "getZones"
    }
    zones = requests.post(f"https://{instance}/api", json=data, headers=headers)
    if zones.status_code != 200:
        return {"status": "Error connecting to Varo"}
    if not zones.json()["success"]:
        return {"status": "Error connecting to Varo"}
    
    zones = zones.json()["data"]
    for zone in zones:
        if zone["name"] == domain:
            return {"status": "Domain already exists"}
        
    # Check domain is owned by user
    wallet = authentication.split(":")[0]
    owned = account.getDomains(wallet)
    # Only keep owned domains ["name"]
    ownedNames = [domain["name"] for domain in owned]
    if domain not in ownedNames:
        return {"status": "Domain not owned by user"}
    
    data = {
        "action": "createZone",
        "domain": domain
    }
    response = requests.post(f"https://{instance}/api", json=data, headers=headers)
    if response.status_code != 200:
        return {"status": "Error connecting to Varo"}
    if not response.json()["success"]:
        return {"status": "Error connecting to Varo"}
    zoneID = response.json()["data"]["zone"]
    data = {
        "action": "showZone",
        "zone": zoneID
    }
    response = requests.post(f"https://{instance}/api", json=data, headers=headers)
    if response.status_code != 200:
        return {"status": "Error connecting to Varo"}
    if not response.json()["success"]:
        return {"status": "Error connecting to Varo"}
    zone = response.json()["data"]
    
    dns = []
    for ns in zone['NS']:
        dns.append({'type': 'NS', 'value': ns})
    ds = zone['DS']
    ds = ds.split(' ')
    dns.append({'type': 'DS', 'keyTag': int(ds[0]), 'algorithm': int(ds[1]), 'digestType': int(ds[2]), 'digest': ds[3]})
    dns = json.dumps(dns)
    response = account.setDNS(authentication,domain,dns)

    return {"status": "Success"}