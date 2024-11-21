import json
import account
import requests
import os
import dotenv

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
        "description": "You need to set varo_instance to the ICANN domain of the chosen Varo instance and varo_api to your varo API key before you can connect",
        "params": {},
        "returns": {
            "status": 
            {
                "name": "Status of varo connection",
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
    dotenv.load_dotenv()
    api = os.getenv("varo_api")
    instance = os.getenv("varo_instance")

    if not api or not instance:
        return {"status": "Missing Varo API or instance"}
    
    headers = {"Authorization": f"Bearer {api}"}
    data = {
        "action": "getInfo"
    }
    response = requests.post(f"https://{instance}/api", json=data, headers=headers)
    if response.status_code != 200:
        return {"status": "Error connecting to Varo"}
    if response.json()["success"] != True:
        return {"status": "Error connecting to Varo"}
    return {"status": "Success"}

def addDomain(params, authentication):
    # Add a domain to Varo
    domain = params["domain"]

    dotenv.load_dotenv()
    api = os.getenv("varo_api")
    instance = os.getenv("varo_instance")

    if not api or not instance:
        return {"status": "Missing Varo API or instance"}
    
    headers = {"Authorization": f"Bearer {api}"}
    data = {
        "action": "getZones"
    }
    zones = requests.post(f"https://{instance}/api", json=data, headers=headers)
    if zones.status_code != 200:
        return {"status": "Error connecting to Varo"}
    if zones.json()["success"] != True:
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
    if response.json()["success"] != True:
        return {"status": "Error connecting to Varo"}
    zoneID = response.json()["data"]["zone"]
    data = {
        "action": "showZone",
        "zone": zoneID
    }
    response = requests.post(f"https://{instance}/api", json=data, headers=headers)
    if response.status_code != 200:
        return {"status": "Error connecting to Varo"}
    if response.json()["success"] != True:
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