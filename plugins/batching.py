import json
import account
import requests


# Plugin Data
info = {
    "name": "Batching Functions",
    "description": "This is a plugin that provides multiple functions to batch transactions",  
    "version": "1.0",
    "author": "Nathan.Woodburn/"
}
# https://hsd-dev.org/api-docs/?shell--cli#sendbatch


# Functions
functions = {
    "transfer":{
        "name": "Batch transfer",
        "type": "default",
        "description": "Transfer a ton of domains",
        "params": {
            "domains": {
                "name":"List of domains to transfer (one per line)",
                "type":"longText"
            },
            "address": {
                "name":"Address to transfer to",
                "type":"address"
            }
        },
        "returns": {
            "status":
            {
                "name": "Status",
                "type": "text"
            },
            "transaction": 
            {
                "name": "Hash of the transaction",
                "type": "tx"
            }
        }
    },
    "finalize":{
        "name": "Batch finalize a transfer",
        "type": "default",
        "description": "Finalize transferring a ton of domains", 
        "params": {
            "domains": {
                "name":"List of domains to finalize (one per line)",
                "type":"longText"
            }
        },
        "returns": {
            "status":
            {
                "name": "Status",
                "type": "text"
            },
            "transaction": 
            {
                "name": "Hash of the transaction",
                "type": "tx"
            }
        }
    },
    "cancel":{
        "name": "Batch cancel a transfer",
        "type": "default",
        "description": "Cancel transferring a ton of domains", 
        "params": {
            "domains": {
                "name":"List of domains to cancel (one per line)",
                "type":"longText"
            }
        },
        "returns": {
            "status":
            {
                "name": "Status",
                "type": "text"
            },
            "transaction": 
            {
                "name": "Hash of the transaction",
                "type": "tx"
            }
        }
    },
    "open":{
        "name": "Batch open auctions",
        "type": "default",
        "description": "Open auctions for a ton of domains", 
        "params": {
            "domains": {
                "name":"List of domains to open (one per line)",
                "type":"longText"
            }
        },
        "returns": {
            "status":
            {
                "name": "Status",
                "type": "text"
            },
            "transaction": 
            {
                "name": "Hash of the transaction",
                "type": "tx"
            }
        }
    },
    "bid":{
        "name": "Batch bid on auctions",
        "type": "default",
        "description": "Bid on auctions for a ton of domains",
        "params": {
            "domains": {
                "name":"List of domains to bid on (one per line)",
                "type":"longText"
            },
            "bid": {
                "name":"Bid amount",
                "type":"text"
            },
            "blind": {
                "name":"Blind amount",
                "type":"text"
            }
        },
        "returns": {
            "status":
            {
                "name": "Status",
                "type": "text"
            },
            "transaction": 
            {
                "name": "Hash of the transaction",
                "type": "tx"
            }
        }
    },
    "reveal":{
        "name": "Batch reveal bids",
        "type": "default",
        "description": "Reveal bids for tons of auctions",  
        "params": {
            "domains": {
                "name":"List of domains to reveal (one per line)",
                "type":"longText"
            }
        },
        "returns": {
            "status":
            {
                "name": "Status",
                "type": "text"
            },
            "transaction": 
            {
                "name": "Hash of the transaction",
                "type": "tx"
            }
        }
    },
    "redeem":{
        "name": "Batch redeem bids",
        "type": "default",
        "description": "Redeem lost bids to get funds back",   
        "params": {
            "domains": {
                "name":"List of domains to redeem (one per line)",
                "type":"longText"
            }
        },
        "returns": {
            "status":
            {
                "name": "Status",
                "type": "text"
            },
            "transaction": 
            {
                "name": "Hash of the transaction",
                "type": "tx"
            }
        }
    },
    "register":{
        "name": "Batch register domains",
        "type": "default",
        "description": "Register domains won in auction",
        "params": {
            "domains": {
                "name":"List of domains to redeem (one per line)",
                "type":"longText"
            }
        },
        "returns": {
            "status":
            {
                "name": "Status",
                "type": "text"
            },
            "transaction": 
            {
                "name": "Hash of the transaction",
                "type": "tx"
            }
        }
    },
    "renew":{
        "name": "Batch renew domains", 
        "type": "default",
        "description": "Renew a ton of domain",
        "params": {
            "domains": {
                "name": "Domains to renew (one per line)",
                "type": "longText"
            }
        },
        "returns": {
            "status": {
                "name": "Status",
                "type": "text"
            },
            "transaction": 
            {
                "name": "Hash of the transaction",
                "type": "tx"
            }
        }
    },
    "advancedBid":{
        "name": "Bid on domains with csv",
        "type": "default",
        "description": "Bid on domains using a csv format",
        "params": {
            "bids": {
                "name":"List of bids in format `domain,bid,blind` (one per line)",
                "type":"longText"
            }
        },
        "returns": {
            "status":
            {
                "name": "Status",
                "type": "text"
            },
            "transaction": 
            {
                "name": "Hash of the transaction",
                "type": "tx"
            }
        }
    },
    "advancedBatch":{
        "name": "Batch transactions with csv",
        "type": "default",
        "description": "Batch transactions using a csv format",
        "params": {
            "transactions": {
                "name":"List of transactions in format `type,domain,param1,param2` (one per line) Eg.<br>TRANSFER,woodburn1,hs1q4rkfe5df7ss6wzhnw388hv27we0hp7ha2np0hk<br>OPEN,woodburn2",
                "type":"longText"
            }
        },
        "returns": {
            "status":
            {
                "name": "Status",
                "type": "text"
            },
            "transaction": 
            {
                "name": "Hash of the transaction",
                "type": "tx"
            }
        }
    }
}

def sendBatch(batch, authentication):
    response = account.sendBatch(authentication, batch)
    return response


def transfer(params, authentication):
    domains = params["domains"]
    address = params["address"]
    domains = domains.splitlines()
    domains = [x.strip() for x in domains]
    domains = [x for x in domains if x != ""]

    wallet = authentication.split(":")[0]
    owned = account.getDomains(wallet)
    # Only keep owned domains ["name"]
    ownedNames = [domain["name"] for domain in owned]

    for domain in domains:        
        if domain not in ownedNames:
            return {
                "status":f"Domain {domain} not owned",
                "transaction":None
            }
    
    batch = []
    for domain in domains:
        batch.append(['TRANSFER', domain, address])

    response = sendBatch(batch, authentication)
    if 'error' in response:
        return {
            "status":response['error']['message'],
            "transaction":None
        }

    return {
        "status":"Sent batch successfully",
        "transaction":response['hash']
    }

def simple(batchType,params, authentication):
    domains = params["domains"]
    domains = domains.splitlines()
    domains = [x.strip() for x in domains]
    domains = [x for x in domains if x != ""]

    batch = []
    for domain in domains:
        batch.append([batchType, domain])

    response = sendBatch(batch, authentication)
    if 'error' in response:
        return {
            "status":response['error']['message'],
            "transaction":None
        }

    return {
        "status":"Sent batch successfully",
        "transaction":response['hash']
    }

def finalize(params, authentication):
    return simple("FINALIZE",params,authentication)

def cancel(params, authentication):
    return simple("CANCEL",params,authentication)

def open(params, authentication):
    return simple("OPEN",params,authentication)

def bid(params, authentication):
    domains = params["domains"]
    domains = domains.splitlines()
    domains = [x.strip() for x in domains]
    domains = [x for x in domains if x != ""]

    try:
        bid = float(params["bid"])
        blind = float(params["blind"])
        blind+=bid
    except:
        return {
            "status":"Invalid bid amount",
            "transaction":None
        }

    batch = []
    for domain in domains:
        batch.append(['BID', domain, bid, blind])

    print(batch)
    response = sendBatch(batch, authentication)
    if 'error' in response:
        return {
            "status":response['error']['message'],
            "transaction":None
        }
    
    return {
        "status":"Sent batch successfully",
        "transaction":response['hash']
    }

def reveal(params, authentication):
    return simple("REVEAL",params,authentication)

def redeem(params, authentication):
    return simple("REDEEM",params,authentication)

def register(params, authentication):
    domains = params["domains"]
    domains = domains.splitlines()
    domains = [x.strip() for x in domains]
    domains = [x for x in domains if x != ""]

    batch = []
    for domain in domains:
        batch.append(['UPDATE', domain,{"records": []}])

    print(batch)
    response = sendBatch(batch, authentication)
    if 'error' in response:
        return {
            "status":response['error']['message'],
            "transaction":None
        }
    
    return {
        "status":"Sent batch successfully",
        "transaction":response['hash']
    }

def renew(params, authentication):
    return simple("RENEW", params, authentication)

def advancedBid(params, authentication):
    bids = params["bids"]
    bids = bids.splitlines()
    bids = [x.strip() for x in bids]
    bids = [x for x in bids if x != ""]
    
    batch = []
    for bid in bids:
        # Split the bid
        line = bid.split(",")
        domain = line[0]
        bid = float(line[1])
        blind = float(line[2])
        blind+=bid
        batch.append(['BID', domain, bid, blind])

    print(batch)
    response = sendBatch(batch, authentication)
    if 'error' in response:
        return {
            "status":response['error']['message'],
            "transaction":None
        }
    
    return {
        "status":"Sent batch successfully",
        "transaction":response['hash']
    }

def advancedBatch(params, authentication):
    transactions = params["transactions"]
    transactions = transactions.splitlines()
    transactions = [x.strip() for x in transactions]
    transactions = [x for x in transactions if x != ""]
    
    batch = []
    for transaction in transactions:
        # Split the bid
        line = transaction.split(",")
        line[0] = line[0].upper()
        batch.append(line)

    print(batch)
    response = sendBatch(batch, authentication)
    if 'error' in response:
        return {
            "status":response['error']['message'],
            "transaction":None
        }
    
    return {
        "status":"Sent batch successfully",
        "transaction":response['hash']
    }
