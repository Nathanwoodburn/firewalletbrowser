from handywrapper import api
import os
import dotenv
import requests


dotenv.load_dotenv()

APIKEY = os.getenv("hsd_api")
hsd = api.hsd(APIKEY)
hsw = api.hsw(APIKEY)

# Verify the connection
response = hsd.getInfo()



def check_account(cookie: str):
    # Check the account
    if cookie.count(":") < 1:
        return False

    account = cookie.split(":")[0]
    password = ":".join(cookie.split(":")[1:])


    # Check if the account is valid
    info = hsw.getAccountInfo(account, 'default')
    if 'error' in info:
        return False

    return account


def getBalance(account: str):
    # Get the total balance
    info = hsw.getBalance('default',account)
    if 'error' in info:
        return {'available': 0, 'total': 0}

    total = info['confirmed']
    available = total - info['lockedConfirmed']

    # Convert to HNS
    total = total / 1000000
    available = available / 1000000

    # Only keep 2 decimal places
    total = round(total, 2)
    available = round(available, 2)

    return {'available': available, 'total': total}

def getPendingTX(account: str):
    # Get the pending transactions
    info = hsw.getWalletTxHistory()
    if 'error' in info:
        return 0
    
    pending = 0
    for tx in info:
        if tx['confirmations'] < 1:
            pending += 1

    return pending


def getDomains(account):
    # Get the domains
    # info = hsw.getWalletNames(account)
    # if 'error' in info:
    #     return []

    # use requests to get the domains
    response = requests.get(f"http://x:{APIKEY}@127.0.0.1:12039/wallet/{account}/name?own=true")
    info = response.json()
    return info

def getTransactions(account):
    # Get the transactions
    info = hsw.getWalletTxHistory(account)
    if 'error' in info:
        return []
    return info