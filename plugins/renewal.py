import json
import account
import requests
import os

# Plugin Data
info = {
    "name": "Batch Renew Domains",
    "description": "Renew the next 100 domains",
    "version": "1.0",
    "author": "Nathan.Woodburn/"
}

# Functions
functions = {
    "main":{
        "name": "Renew",
        "type": "default",
        "description": "Renew the next 100 domains in one transaction. Please wait for at least 1 block confirmation before renewing the next 100 domains",
        "params": {},
        "returns": {
            "status": 
            {
                "name": "Status of the function",
                "type": "text"
            },
            "transaction":
            {
                "name": "Transaction ID",
                "type": "tx"
            }
        }
    }
}

def main(params, authentication):
    password = authentication.split(":")[1]
    wallet = authentication.split(":")[0]
    domains = account.getDomains(wallet)
    domains = sorted(domains, key=lambda k: k['renewal'])
        
    names = []
    for domain in domains:
        name = domain["name"]
        names.append(name)
    
    # Split names into batches of 100
    batches = []
    for i in range(0, len(names), 100):
        batches.append(names[i:i+100])

    # Unlock wallet
    api_key = os.getenv("hsd_api")
    ip = os.getenv("hsd_ip")
    if api_key is None:
        print("API key not set")
        return {"status": "API key not set", "transaction": "None"}
    response = requests.post(f'http://x:{api_key}@{ip}:12039/wallet/{wallet}/unlock',
                             json={'passphrase': password, 'timeout': 600})
    if response.status_code != 200:
        print("Failed to unlock wallet")
        print(f'Status code: {response.status_code}')
        print(f'Response: {response.text}')
        return {"status": "Failed unlocking wallet", "transaction": "None"}


    tx = "None"
    for batch in batches:            
        batch = []

        for domain in names:
            batch.append(f'["RENEW", "{domain}"]')
        
        
        batchTX = "[" + ", ".join(batch) + "]"
        responseContent = f'{{"method": "sendbatch","params":[ {batchTX} ]}}'
        response = requests.post(f'http://x:{api_key}@{ip}:12039', data=responseContent)
        if response.status_code != 200:
            print("Failed to create batch",flush=True)
            print(f'Status code: {response.status_code}',flush=True)
            print(f'Response: {response.text}',flush=True)
            return {"status": "Failed", "transaction": "None"}

        batch = response.json()
        # Verify the batch
        print("Verifying tx...")
        if batch["error"]:
            if batch["error"] != "":
                print("Failed to verify batch",flush=True)
                print(batch["error"]["message"],flush=True)
                return {"status": f"Failed: {batch['error']['message']}", "transaction": "None"}
        
        if 'result' in batch:
            if batch['result'] != None:
                tx = batch['result']['hash']
        return {"status": "Success", "transaction": tx}
        # Note only one batch can be sent at a time
    