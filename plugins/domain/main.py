import json
import account


functions = {
    "bids": {
        "name": "Bid info",
        "type": "domain",
        "description": "Check when the domain was last updated",
        "params": {
            "domain": {
                "name":"domain to check",
                "type":"domain"
            }
        },
        "returns": {
            "highest": 
            {
                "name": "Highest bid",
                "type": "text"
            },
            "paid": 
            {
                "name": "Amount paid in auction",
                "type": "text"
            }
        }
    }
}

def listFunctions():
    return functions

def runFunction(function, params, authentication):
    if function == "bids":
        return bids(params['domain'], authentication)
    else:
        return "Function not found"


def bids(domain, authentication):
    wallet = authentication.split(":")[0]
    data = account.getDomain(domain)
    value = str(account.convertHNS(data['info']['value'])) + " HNS"
    highest = str(account.convertHNS(data['info']['highest'])) + " HNS"
    

    return {"highest": highest,"paid":value}