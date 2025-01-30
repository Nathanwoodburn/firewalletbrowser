import json
import account
import requests

# Plugin Data
info = {
    "name": "TX Count",
    "description": "Plugin for checking how many txs are in a wallet",
    "version": "1.0",
    "author": "Nathan.Woodburn/"
}

# Functions
functions = {
    "main":{
        "name": "List TXs",
        "type": "default",
        "description": "Get TXs",
        "params": {},
        "returns": {
            "txs": 
            {
                "name": "Transactions",
                "type": "text"
            }
        }
    }
}

def main(params, authentication):
    wallet = authentication.split(":")[0]
    txCount = 0
    page = 1
    while True:
        txs = account.getTransactions(wallet,page)
        if len(txs) == 0:
            break
        txCount += len(txs)
        page += 1

    return {"txs": f'Total TXs: {txCount}'}
    