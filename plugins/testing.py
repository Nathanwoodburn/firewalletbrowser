import json
import account
import requests

# Plugin Data
info = {
    "name": "Testing tools",
    "description": "Testing tools",
    "version": "1.0",
    "author": "Nathan.Woodburn/"
}

# Functions
functions = {
    "generate":{
        "name": "Generate blocks",
        "type": "default",
        "description": "Generate blocks to your wallet",
        "params": {
            "numblocks": {
                "name":"Number of blocks to generate",
                "type":"number"
            },
            "address": {
                "name":"Address to generate to",
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

def generate(params, authentication):
    # hsd-cli rpc generatetoaddress $numblocks $address
    number = params["numblocks"]
    address = params["address"]
    if number == "" or int(number) < 1:
        number = 1
    
    if address == "":
        wallet = authentication.split(":")[0]
        address = account.getAddress(wallet)
    
    print(f"Generating {number} blocks to {address}")
    blocks = account.hsd.rpc_generateToAddress(address,number)
    return {"status": f"Successfully generated {number} blocks to {address}"}
    