import json
import account


functions = {
    "check": {
        "name": "Domain Check",
        "description": "Check if domains in file are owned by the wallet",
        "params": {
            "domains": {
                "name":"List of domains to check",
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
    },
    "transfer":{
        "name": "Bulk Transfer Domains",
        "description": "Transfer domains to another wallet",
        "params": {
            "address": {
                "name":"Address to transfer to",
                "type":"address"
            },
            "domains": {
                "name":"List of domains to transfer",
                "type":"longText"
            }
        },
        "returns": {
            "hash": {
                "name": "Hash of the transaction",
                "type": "tx"
            },
            "address":{
                "name": "Address of the new owner",
                "type": "text"
            }
        }
    },
    "dns":{
        "name": "Set DNS for Domains",
        "description": "Set DNS for domains",
        "params": {
            "domains": {
                "name":"List of domains to set DNS for",
                "type":"longText"
            },
            "dns": {
                "name":"DNS",
                "type":"dns"
            }
        },
        "returns": {
            "hash": {
                "name": "Hash of the transaction",
                "type": "tx"
            },
            "dns":{
                "name": "DNS",
                "type": "dns"
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
    elif function == "transfer":
        return transfer(params['address'], params['domains'], authentication)
    elif function == "dns":
        return dns(params['domains'],params['dns'],authentication)
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


def transfer(address, domains, authentication):
    return {"hash":"f921ffe1bb01884bf515a8079073ee9381cb93a56b486694eda2cce0719f27c0","address":address}

def dns(domains,dns,authentication):
    return {"hash":"f921ffe1bb01884bf515a8079073ee9381cb93a56b486694eda2cce0719f27c0","dns":dns}