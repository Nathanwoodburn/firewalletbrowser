import json
import account
import requests
import threading
import os
import time

KEY = account.HSD_API
IP = account.HSD_IP
PORT = account.HSD_WALLET_PORT


if not os.path.exists("user_data"):
    os.mkdir("user_data")

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
    },
    "disable":{
        "name": "Disable Automations",
        "type": "default",
        "description": "Disable Automations for this wallet",
        "params": {},
        "returns": {
            "Status": 
            {
                "name": "Status",
                "type": "text"
            }
        }
    },
    "enable":{
        "name": "Enable Automations",
        "type": "default",
        "description": "Enable Automations for this wallet",
        "params": {},
        "returns": {
            "Status": 
            {
                "name": "Status",
                "type": "text"
            }
        }
    },
    "list":{
        "name": "List Disabled Wallets",
        "type": "default",
        "description": "List wallets with automations disabled",
        "params": {},
        "returns": {
            "wallets": 
            {
                "name": "List of wallets",
                "type": "list"
            }
        }
    }
}

started = False

# Main entry point only lets the main function run every 5 mins
def automation(params, authentication):
    global started
    
    wallet = authentication.split(":")[0]
    if os.path.exists(f"user_data/{wallet}.autoRenew"):
        return {"Status": "Automations disabled"}
    
    if started:
        return {"Status": "Automations running"}
    started = True    

    threading.Thread(target=automations_background, args=(authentication,)).start()
    return {"Status": "Starting Automations..."}

def disable(params, authentication):
    # Create walletname file in user_data
    wallet = authentication.split(":")[0]
    if not os.path.exists("user_data"):
        os.mkdir("user_data")
    with open(f"user_data/{wallet}.autoRenew", "w") as f:
        f.write(f"This file is used to disable automations for '{wallet}' wallet.\nDelete this file to enable automations.")
    return {"Status": "Disabled Automations"}

def enable(params, authentication):
    # Delete walletname file in user_data
    wallet = authentication.split(":")[0]
    if os.path.exists(f"user_data/{wallet}.autoRenew"):
        os.remove(f"user_data/{wallet}.autoRenew")

    return {"Status": "Enabled Automations"}

def list(params, authentication):
    wallets = []
    for file in os.listdir("user_data"):
        if file.endswith(".autoRenew"):
            wallets.append(file[:-10])
    return {"wallets": wallets}

# Background function to run the automations
def automations_background(authentication):

    while True:
        # Get account details
        account_name = account.check_account(authentication)
        password = ":".join(authentication.split(":")[1:])

        if account_name == False:
            return {
                "error": {
                    "message": "Invalid account"
                }
            }
        
        if os.path.exists(f"user_data/{account_name}.autoRenew"):
            print("Skipping Automations")
            time.sleep(300)            
            continue
        print("Running automations")
        try:
            # Try to select and login to the wallet
            response = account.hsw.rpc_selectWallet(account_name)
            if response['error'] is not None:
                return
            response = account.hsw.rpc_walletPassphrase(password,30)
            if response['error'] is not None:
                return
            # Try to send the batch of all renew, reveal and redeem actions
            requests.post(f"http://x:{KEY}@{IP}:{PORT}",json={"method": "sendbatch","params": [[["RENEW"]]]})
            requests.post(f"http://x:{KEY}@{IP}:{PORT}",json={"method": "sendbatch","params": [[["REVEAL"]]]})
            requests.post(f"http://x:{KEY}@{IP}:{PORT}",json={"method": "sendbatch","params": [[["REDEEM"]]]})
        except Exception as e:
            print(e)

        # Sleep for 5 mins before running again
        time.sleep(300)