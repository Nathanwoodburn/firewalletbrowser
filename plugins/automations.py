import json
import account
import requests
import threading
import os
import time

APIKEY = os.environ.get("hsd_api")
ip = os.getenv("hsd_ip")
if ip is None:
    ip = "localhost"


# Plugin Data
info = {
    "name": "Automations",
    "description": "This plugin will automatically renew domains, reveal and redeem bids.",
    "version": "1.0",
    "author": "Nathan.Woodburn/"
}


# Functions
functions = {
    "automation":{
        "name": "Function to automate",
        "type": "dashboard",
        "description": "This used type dashboard to trigger the function whenever you access the dashboard.",
        "params": {},
        "returns": {
            "Status": 
            {
                "name": "Status of the automation",
                "type": "text"
            }
        }
    }
}

started = False

# Main entry point only lets the main function run every 5 mins
def automation(params, authentication):
    global started
    
    if started:
        return {"Status": "Auto Renews running"}
    started = True
    threading.Thread(target=automations_background, args=(authentication,)).start()
    return {"Status": "Started Auto Renews"}

# Background function to run the automations
def automations_background(authentication):
    while True:
        print("Running automations")
        # Get account details
        account_name = account.check_account(authentication)
        password = ":".join(authentication.split(":")[1:])

        if account_name == False:
            return {
                "error": {
                    "message": "Invalid account"
                }
            }

        try:
            # Try to select and login to the wallet
            response = account.hsw.rpc_selectWallet(account_name)
            if response['error'] is not None:
                return
            response = account.hsw.rpc_walletPassphrase(password,10)
            if response['error'] is not None:
                return
            # Try to send the batch of all renew, reveal and redeem actions
            requests.post(f"http://x:{APIKEY}@{ip}:12039",json={"method": "sendbatch","params": [[["RENEW"]]]})
            requests.post(f"http://x:{APIKEY}@{ip}:12039",json={"method": "sendbatch","params": [[["REVEAL"]]]})
            requests.post(f"http://x:{APIKEY}@{ip}:12039",json={"method": "sendbatch","params": [[["REDEEM"]]]})
        except Exception as e:
            print(e)

        # Sleep for 5 mins before running again
        time.sleep(300)