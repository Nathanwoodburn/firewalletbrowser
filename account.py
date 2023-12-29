from handywrapper import api
import os
import dotenv
import requests
import re
import domainLookup
import json


dotenv.load_dotenv()

APIKEY = os.getenv("hsd_api")
hsd = api.hsd(APIKEY)
hsw = api.hsw(APIKEY)

# Verify the connection
response = hsd.getInfo()



def check_account(cookie: str):
    if cookie is None:
        return False

    # Check the account
    if cookie.count(":") < 1:
        return False

    account = cookie.split(":")[0]
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

def getAddress(account: str):
    # Get the address
    info = hsw.getAccountInfo(account, 'default')
    if 'error' in info:
        return ''
    return info['receiveAddress']

def getPendingTX(account: str):
    # Get the pending transactions
    info = hsw.getWalletTxHistory(account)
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


def check_address(address: str, allow_name: bool = True, return_address: bool = False):
    # Check if the address is valid
    if address.startswith('@'):
        # Check if the address is a name
        if not allow_name and not return_address:
            return 'Invalid address'
        elif not allow_name and return_address:
            return False
        return check_hip2(address[1:])
    
    # Check if the address is a valid HNS address
    response = requests.post(f"http://x:{APIKEY}@127.0.0.1:12037",json={
        "method": "validateaddress",
        "params": [address]
    }).json()
    if response['error'] is not None:
        if return_address:
            return False
        return 'Invalid address'
    
    if response['result']['isvalid'] == True:
        if return_address:
            return address
        return 'Valid address'
    
    if return_address:
        return False
    return 'Invalid address'


def check_hip2(domain: str):
    # Check if the domain is valid
    domain = domain.lower()

    if re.match(r'^[a-zA-Z0-9\-\.]{1,63}$', domain) is None:
        return 'Invalid address'
    
    address = domainLookup.hip2(domain)
    if address.startswith("Hip2: "):
        return address

    if not check_address(address, False,True):
        return 'Hip2: Lookup succeeded but address is invalid'
    return address



def send(account,address,amount):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])




    response = hsw.rpc_selectWallet(account_name)
    if response['error'] is not None:
        return {
            "error": response['error']['message']
        }

    response = hsw.rpc_walletPassphrase(password,10)
    # Unlock the account
    # response = requests.post(f"http://x:{APIKEY}@127.0.0.1:12039/wallet/{account_name}/unlock",
        # json={"passphrase": password,"timeout": 10})
    if response['error'] is not None:
        return {
            "error": response['error']['message']
        }

    response = hsw.rpc_sendToAddress(address,amount)
    if response['error'] is not None:
        return {
            "error": response['error']['message']
        }
    return {
        "tx": response['result']
    }

def getDomain(domain: str):
    # Get the domain
    response = hsd.rpc_getNameInfo(domain)
    if response['error'] is not None:
        return {
            "error": response['error']['message']
        }
    return response['result']

def renewDomain(account,domain):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if account_name == False:
        return {
            "error": "Invalid account"
        }

    response = hsw.sendRENEW(account_name,password,domain)
    return response

def getDNS(domain: str):
    # Get the DNS
    response = hsd.rpc_getNameResource(domain)
    if response['error'] is not None:
        return {
            "error": response['error']['message']
        }
    return response['result']['records']


def getNodeSync():
    response = hsd.getInfo()
    sync = response['chain']['progress']*100
    sync = round(sync, 2)
    return sync


def getBids(account, domain):
    response = hsw.getWalletBidsByName(domain,account)
    return response

def getReveals(account,domain):
    return hsw.getWalletRevealsByName(domain,account)


def getRevealTX(reveal):
    prevout = reveal['prevout']
    hash = prevout['hash']
    index = prevout['index']
    tx = hsd.getTxByHash(hash)
    revealAddress = tx['outputs'][index]['address']

    for input in tx['inputs']:
        if input['coin']['address'] == revealAddress:
            return input['prevout']['hash']
    return False
    


def rescan_auction(account,domain):
    # Get height of the start of the auction
    response = hsw.rpc_selectWallet(account)
    response = hsd.rpc_getNameInfo(domain)
    if 'result' not in response:
        return {
            "error": "Invalid domain"
        }
    if 'bidPeriodStart' not in response['result']['info']['stats']:
        return {
            "error": "Not in auction"
        }
    height = response['result']['info']['height']-1
    response = hsw.rpc_importName(domain,height)
    return response


def bid(account,domain,bid,blind):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if account_name == False:
        return {
            "error": "Invalid account"
        }
    
    bid = int(bid)*1000000
    lockup = int(blind)*1000000 + bid

    try:
        response = hsw.sendBID(account_name,password,domain,bid,lockup)
        return response
    except Exception as e:
        return {
            "error": str(e)
        }
    

def openAuction(account,domain):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if account_name == False:
        return {
            "error": "Invalid account"
        }

    try:
        response = hsw.sendOPEN(account_name,password,domain)
        return response
    except Exception as e:
        return {
            "error": str(e)
        }