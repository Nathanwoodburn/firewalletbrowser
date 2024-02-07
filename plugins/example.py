import json
import account
import requests


# Plugin Data
info = {
    "name": "Example Plugin",
    "description": "This is a plugin to be used as an example",
    "version": "1.0",
    "author": "Nathan.Woodburn/"
}


# Functions
functions = {
    "search":{
        "name": "Search Owned",
        "type": "default",
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
        "type": "default",
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
        "type": "default",
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
    },
    "niami": {
        "name": "Niami info",
        "type": "domain",
        "description": "Check the domains niami rating",
        "params": {},
        "returns": {
            "rating": 
            {
                "name": "Niami Rating",
                "type": "text"
            }
        }
    },
    "niamiSearch": {
        "name": "Niami info",
        "type": "search",
        "description": "Check the domains niami rating",
        "params": {},
        "returns": {
            "rating": 
            {
                "name": "Niami Rating",
                "type": "text"
            }
        }
    },
    "connections":{
        "name": "HSD Connections",
        "type": "dashboard",
        "description": "Show the number of connections the HSD node is connected to",
        "params": {},
        "returns": {
            "connections": 
            {
                "name": "HSD Connections",
                "type": "text"
            }
        }
    }
}

def check(params, authentication):
    domains = params["domains"]
    domains = domains.splitlines()

    wallet = authentication.split(":")[0]
    owned = account.getDomains(wallet)
    # Only keep owned domains ["name"]
    ownedNames = [domain["name"] for domain in owned]

    domains = [domain for domain in domains if domain in ownedNames]
    

    return {"domains": domains}

def search(params, authentication):
    search = params["search"]
    wallet = authentication.split(":")[0]
    owned = account.getDomains(wallet)
    # Only keep owned domains ["name"]
    ownedNames = [domain["name"] for domain in owned]

    domains = [domain for domain in ownedNames if search in domain]

    return {"domains": domains}


def transfer(params, authentication):
    address = params["address"]
    return {"hash":"f921ffe1bb01884bf515a8079073ee9381cb93a56b486694eda2cce0719f27c0","address":address}

def dns(params,authentication):
    dns = params["dns"]
    return {"hash":"f921ffe1bb01884bf515a8079073ee9381cb93a56b486694eda2cce0719f27c0","dns":dns}

def niami(params, authentication):
    domain = params["domain"]
    print(domain)
    response = requests.get(f"https://api.handshake.niami.io/domain/{domain}")
    print(response.text)
    data = response.json()["data"]
    rating = str(data["rating"]["score"]) + " (" + data["rating"]["rarity"] + ")"
    return {"rating":rating}

def niamiSearch(params, authentication):
    return niami(params, authentication)


def connections(params,authentication):
    outbound = account.hsd.getInfo()['pool']['outbound']
    return {"connections": outbound}