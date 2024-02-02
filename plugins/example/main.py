import json
import account


functions = {
    "check": {
        "name": "Domain Check",
        "description": "Check if domains in file are owned by the wallet",
        "params": {
            "domains": {
                "name":"File of domains to check",
                "type":"longText"
            }
        },
        "returns": {
            "domains": 
            {
                "name": "List of owned domains",
                "type": "list"
            }
        }
    },
    "search":{
        "name": "Search Owned",
        "description": "Search for owned domains containing a string",
        "params": {
            "search": {
                "name":"Search string",
                "type":"text"
            }
        },
        "returns": {
            "domains": 
            {
                "name": "List of owned domains",
                "type": "list"
            }
        }
    }
}

def listFunctions():
    return functions

def runFunction(function, params, authentication):
    if function == "check":
        return check(params['domains'], authentication)
    elif function == "search":
        return search(params['search'], authentication)
    else:
        return "Function not found"


def check(domains, authentication):
    domains = domains.splitlines()

    wallet = authentication.split(":")[0]
    owned = account.getDomains(wallet)
    # Only keep owned domains ["name"]
    ownedNames = [domain["name"] for domain in owned]

    domains = [domain for domain in domains if domain in ownedNames]
    

    return {"domains": domains}

def search(search, authentication):
    wallet = authentication.split(":")[0]
    owned = account.getDomains(wallet)
    # Only keep owned domains ["name"]
    ownedNames = [domain["name"] for domain in owned]

    domains = [domain for domain in ownedNames if search in domain]

    return {"domains": domains}

