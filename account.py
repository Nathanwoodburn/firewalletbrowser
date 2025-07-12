from datetime import datetime, timedelta
from handywrapper import api
import os
import dotenv
import requests
import re
import domainLookup
import json
import time

dotenv.load_dotenv()

HSD_API = os.getenv("HSD_API")
HSD_IP = os.getenv("HSD_IP")
if HSD_IP is None:
    HSD_IP = "localhost"

HSD_NETWORK = os.getenv("HSD_NETWORK")
HSD_WALLET_PORT = 12039
HSD_NODE_PORT = 12037

if not HSD_NETWORK:
    HSD_NETWORK = "main"
else:
    HSD_NETWORK = HSD_NETWORK.lower()

if HSD_NETWORK == "simnet":
    HSD_WALLET_PORT = 15039
    HSD_NODE_PORT = 15037
elif HSD_NETWORK == "testnet":
    HSD_WALLET_PORT = 13039
    HSD_NODE_PORT = 13037
elif HSD_NETWORK == "regtest":
    HSD_WALLET_PORT = 14039
    HSD_NODE_PORT = 14037


SHOW_EXPIRED = os.getenv("SHOW_EXPIRED")
if SHOW_EXPIRED is None:
    SHOW_EXPIRED = False

hsd = api.hsd(HSD_API, HSD_IP, HSD_NODE_PORT)
hsw = api.hsw(HSD_API, HSD_IP, HSD_WALLET_PORT)

cacheTime = 3600

# Verify the connection
response = hsd.getInfo()

EXCLUDE = ["primary"]
if os.getenv("EXCLUDE") is not None:
    EXCLUDE = os.getenv("EXCLUDE").split(",")


def hsdConnected():
    if hsdVersion() == -1:
        return False
    return True


def hsdVersion(format=True):
    info = hsd.getInfo()
    if 'error' in info:
        return -1
    if format:
        return float('.'.join(info['version'].split(".")[:2]))
    else:
        return info['version']


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


def check_password(cookie: str, password: str):
    account = check_account(cookie)
    if account == False:
        return False

    # Check if the password is valid
    info = hsw.rpc_selectWallet(account)
    if info['error'] is not None:
        return False
    info = hsw.rpc_walletPassphrase(password, 1)
    if info['error'] is not None:
        if info['error']['message'] != "Wallet is not encrypted.":
            return False
    return True


def createWallet(account: str, password: str):
    if not hsdConnected():
        return {
            "error": {
                "message": "Node not connected"
            }
        }
    # Create the account
    # Python wrapper doesn't support this yet
    response = requests.put(get_wallet_api_url(f"wallet/{account}"))
    if response.status_code != 200:
        return {
            "error": {
                "message": "Error creating account"
            }
        }

    # Get seed
    seed = hsw.getMasterHDKey(account)
    seed = seed['mnemonic']['phrase']

    # Encrypt the wallet (python wrapper doesn't support this yet)
    response = requests.post(get_wallet_api_url(f"/wallet/{account}/passphrase"),
                             json={"passphrase": password})

    return {
        "seed": seed,
        "account": account,
        "password": password
    }


def importWallet(account: str, password: str, seed: str):
    if not hsdConnected():
        return {
            "error": {
                "message": "Node not connected"
            }
        }

    # Import the wallet
    data = {
        "passphrase": password,
        "mnemonic": seed,
    }

    response = requests.put(get_wallet_api_url(f"/wallet/{account}"), json=data)
    if response.status_code != 200:
        return {
            "error": {
                "message": "Error creating account"
            }
        }

    return {
        "seed": seed,
        "account": account,
        "password": password
    }


def listWallets():
    # List the wallets
    response = hsw.listWallets()

    # Check if response is json or an array
    if isinstance(response, list):
        # Remove excluded wallets
        response = [wallet for wallet in response if wallet not in EXCLUDE]

        return response
    return ['Wallet not connected']


def selectWallet(account: str):
    # Select wallet
    response = hsw.rpc_selectWallet(account)
    if response['error'] is not None:
        return {
            "error": {
                "message": response['error']['message']
            }
        }

def getBalance(account: str):
    # Get the total balance
    info = hsw.getBalance('default', account)
    if 'error' in info:
        return {'available': 0, 'total': 0}

    total = info['confirmed']
    available = total - info['lockedConfirmed']
    locked = info['lockedConfirmed'] / 1000000

    # Convert to HNS
    total = total / 1000000
    available = available / 1000000

    domains = getDomains(account)
    domainValue = 0
    for domain in domains:
        if domain['state'] == "CLOSED":
            domainValue += domain['value']
    total = total - (domainValue/1000000)
    locked = locked - (domainValue/1000000)

    # Only keep 2 decimal places
    total = round(total, 2)
    available = round(available, 2)

    return {'available': available, 'total': total, 'locked': locked}


def getBlockHeight():
    # Get the block height
    info = hsd.getInfo()
    if 'error' in info:
        return 0
    return info['chain']['height']


def getAddress(account: str):
    # Get the address
    info = hsw.getAccountInfo(account, 'default')
    if 'error' in info:
        return ''
    return info['receiveAddress']


def getPendingTX(account: str):
    pending = 0
    page = 1
    pageSize = 10
    while True:
        txs = getTransactions(account, page, pageSize)
        page += 1
        pendingPage = 0
        for tx in txs:
            if tx['confirmations'] < 1:
                pending += 1
                pendingPage += 1
        if pendingPage < pageSize:
            break
    return pending


def getDomains(account, own=True):
    if own:
        response = requests.get(get_wallet_api_url(f"/wallet/{account}/name?own=true"))
    else:
        response = requests.get(get_wallet_api_url(f"/wallet/{account}/name"))
    info = response.json()

    if SHOW_EXPIRED:
        return info

    # Remove any expired domains
    domains = []
    for domain in info:
        if 'stats' in domain:
            if 'daysUntilExpire' in domain['stats']:
                if domain['stats']['daysUntilExpire'] < 0:
                    continue
        domains.append(domain)

    return domains


def getPageTXCache(account, page, size=100):
    page = f"{page}-{size}"
    if not os.path.exists(f'cache'):
        os.mkdir(f'cache')

    if not os.path.exists(f'cache/{account}_page.json'):
        with open(f'cache/{account}_page.json', 'w') as f:
            f.write('{}')
    with open(f'cache/{account}_page.json') as f:
        pageCache = json.load(f)

    if page in pageCache and pageCache[page]['time'] > int(time.time()) - cacheTime:
        return pageCache[page]['txid']
    return None


def pushPageTXCache(account, page, txid, size=100):
    page = f"{page}-{size}"
    if not os.path.exists(f'cache/{account}_page.json'):
        with open(f'cache/{account}_page.json', 'w') as f:
            f.write('{}')
    with open(f'cache/{account}_page.json') as f:
        pageCache = json.load(f)

    pageCache[page] = {
        'time': int(time.time()),
        'txid': txid
    }
    with open(f'cache/{account}_page.json', 'w') as f:
        json.dump(pageCache, f, indent=4)

    return pageCache[page]['txid']


def getTXFromPage(account, page, size=100):
    if page == 1:
        return getTransactions(account, 1, size)[-1]['hash']

    cached = getPageTXCache(account, page, size)
    if cached:
        return getPageTXCache(account, page, size)
    previous = getTransactions(account, page, size)
    if len(previous) == 0:
        return None
    hash = previous[-1]['hash']
    pushPageTXCache(account, page, hash, size)
    return hash


def getTransactions(account, page=1, limit=100):
    # Get the transactions
    if hsdVersion() < 7:
        if page != 1:
            return []
        info = hsw.getWalletTxHistory(account)
        if 'error' in info:
            return []
        return info[::-1]

    lastTX = None
    if page < 1:
        return []
    if page > 1:
        lastTX = getTXFromPage(account, page-1, limit)

    if lastTX:
        response = requests.get(get_wallet_api_url(f"/wallet/{account}/tx/history?reverse=true&limit={limit}&after={lastTX}"))
    elif page == 1:
        response = requests.get(get_wallet_api_url(f"/wallet/{account}/tx/history?reverse=true&limit={limit}"))
    else:
        return []

    if response.status_code != 200:
        print(response.text)
        return []
    data = response.json()

    # Refresh the cache if the next page is different
    nextPage = getPageTXCache(account, page, limit)
    if nextPage is not None and nextPage != data[-1]['hash']:
        print(f'Refreshing page {page}')
        pushPageTXCache(account, page, data[-1]['hash'], limit)
    return data


def getAllTransactions(account):
    # Get the transactions
    page = 0
    txs = []
    while True:
        txs += getTransactions(account, page, 1000)
        if len(txs) == 0:
            break
        page += 1
    return txs


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
    response = requests.post(get_node_api_url(), json={
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
        return 'Invalid domain'

    address = domainLookup.hip2(domain)
    if address.startswith("Hip2: "):
        return address

    if not check_address(address, False, True):
        return 'Hip2: Lookup succeeded but address is invalid'
    return address


def send(account, address, amount):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])
    response = hsw.rpc_selectWallet(account_name)
    if response['error'] is not None:
        return {
            "error": {
                "message": response['error']['message']
            }
        }

    response = hsw.rpc_walletPassphrase(password, 10)
    # Unlock the account
    if response['error'] is not None:
        if response['error']['message'] != "Wallet is not encrypted.":
            return {
                "error": {
                    "message": response['error']['message']
                }
            }

    response = hsw.rpc_sendToAddress(address, amount)
    if response['error'] is not None:
        return {
            "error": {
                "message": response['error']['message']
            }
        }
    return {
        "tx": response['result']
    }


def isOwnDomain(account, name: str):
    # Get domain
    domain_info = getDomain(name)
    owner = getAddressFromCoin(domain_info['info']['owner']['hash'],domain_info['info']['owner']['index'])
    # Select the account
    hsw.rpc_selectWallet(account)
    account = hsw.rpc_getAccount(owner)

    if 'error' in account and account['error'] is not None:
        return False
    if 'result' not in account:
        return False
    if account['result'] == 'default':
        return True
    return False


def getDomain(domain: str):
    # Get the domain
    response = hsd.rpc_getNameInfo(domain)
    if response['error'] is not None:
        return {
            "error": {
                "message": response['error']['message']
            }
        }
    return response['result']

def getAddressFromCoin(coinhash: str, coinindex = 0):
    # Get the address from the hash
    response = requests.get(get_node_api_url(f"coin/{coinhash}/{coinindex}"))
    if response.status_code != 200:
        return "No Owner"
    data = response.json()
    if 'address' not in data:
        return "No Owner"
    return data['address']


def renewDomain(account, domain):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if account_name == False:
        return {
            "error": {
                "message": "Invalid account"
            }
        }

    response = hsw.sendRENEW(account_name, password, domain)
    return response


def getDNS(domain: str):
    # Get the DNS
    response = hsd.rpc_getNameResource(domain)
    if response['error'] is not None:
        return {
            "error": response['error']['message']
        }
    if 'result' not in response:
        return {
            "error": "No DNS records"
        }
    if response['result'] == None:
        return []

    if 'records' not in response['result']:
        return []
    return response['result']['records']


def setDNS(account, domain, records):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if account_name == False:
        return {
            "error": {
                "message": "Invalid account"
            }
        }

    records = json.loads(records)
    newRecords = []
    TXTRecords = []
    for record in records:
        if record['type'] == 'TXT':
            if 'txt' not in record:
                TXTRecords.append(record['value'])
            else:
                for txt in record['txt']:
                    TXTRecords.append(txt)
        elif record['type'] == 'NS':
            if 'value' in record:
                newRecords.append({
                    'type': 'NS',
                    'ns': record['value']
                })
            elif 'ns' in record:
                newRecords.append({
                    'type': 'NS',
                    'ns': record['ns']
                })
            else:
                return {
                    'error': {
                        'message': 'Invalid NS record'
                    }
                }
            

        elif record['type'] in ['GLUE4', 'GLUE6', "SYNTH4", "SYNTH6"]:
            newRecords.append({
                'type': record['type'],
                'ns': str(record['value']).split(' ')[0],
                'address': str(record['value']).split(' ')[1]
            })
        else:
            newRecords.append(record)

    if len(TXTRecords) > 0:
        newRecords.append({
            'type': 'TXT',
            'txt': TXTRecords
        })
    data = '{"records":'+str(newRecords).replace("'", "\"")+'}'
    response = hsw.sendUPDATE(account_name, password, domain, data)
    return response


def register(account, domain):
    # Maybe add default dns records?
    return setDNS(account, domain, '[]')


def getNodeSync():
    response = hsd.getInfo()
    if 'error' in response:
        return 0

    sync = response['chain']['progress']*100
    sync = round(sync, 2)
    return sync


def getWalletStatus():
    response = hsw.rpc_getWalletInfo()
    if 'error' in response and response['error'] != None:
        return "Error"

    # return response
    walletHeight = response['result']['height']
    # Get the current block height
    nodeHeight = getBlockHeight()

    if walletHeight < nodeHeight:
        return f"Scanning {walletHeight/nodeHeight*100:.2f}%"
    elif walletHeight == nodeHeight:
        return "Ready"
    else:
        return "Error wallet ahead of node"


def getBids(account, domain="NONE"):
    if domain == "NONE":
        response = hsw.getWalletBids(account)
    else:
        response = hsw.getWalletBidsByName(domain, account)
    # Add backup for bids with no value
    bids = []
    for bid in response:
        if 'value' not in bid:
            bid['value'] = -1000000

        # Backup for older HSD versions
        if 'height' not in bid:
            bid['height'] = 0
        bids.append(bid)
    return bids


def getReveals(account, domain):
    return hsw.getWalletRevealsByName(domain, account)


def getPendingReveals(account):
    bids = getBids(account)
    domains = getDomains(account, False)
    pending = []
    for domain in domains:
        if domain['state'] == "REVEAL":
            reveals = getReveals(account, domain['name'])
            for bid in bids:
                if bid['name'] == domain['name']:
                    state_found = False
                    for reveal in reveals:
                        if reveal['own'] == True:
                            if bid['value'] == reveal['value']:
                                state_found = True

                    if not state_found:
                        pending.append(bid)
    return pending


def getPendingRedeems(account, password):
    hsw.rpc_selectWallet(account)
    hsw.rpc_walletPassphrase(password, 10)
    tx = hsw.rpc_createREDEEM('', 'default')
    if tx['error']:
        return []

    pending = []
    try:
        for output in tx['result']['outputs']:
            if output['covenant']['type'] != 5:
                continue
            if output['covenant']['action'] != "REDEEM":
                continue
            nameHash = output['covenant']['items'][0]
            # Try to get the name from hash
            name = hsd.rpc_getNameByHash(nameHash)
            if name['error']:
                pending.append(nameHash)
            else:
                pending.append(name['result'])
    except:
        print("Failed to parse redeems")

    return pending


def getPendingRegisters(account):
    bids = getBids(account)
    domains = getDomains(account, False)
    pending = []
    for domain in domains:
        if domain['state'] == "CLOSED" and domain['registered'] == False:
            for bid in bids:
                if bid['name'] == domain['name']:
                    if bid['value'] == domain['highest']:
                        pending.append(bid)
    return pending


def getPendingFinalizes(account, password):
    tx = createBatch(f'{account}:{password}', [["FINALIZE"]])
    if 'error' in tx:
        return []

    pending = []
    try:
        for output in tx['outputs']:
            if output['covenant']['type'] != 10:
                continue
            if output['covenant']['action'] != "FINALIZE":
                continue
            nameHash = output['covenant']['items'][0]
            # Try to get the name from hash
            name = hsd.rpc_getNameByHash(nameHash)
            if name['error']:
                pending.append(nameHash)
            else:
                pending.append(name['result'])
    except:
        print("Failed to parse finalizes")
    return pending


def getRevealTX(reveal):
    prevout = reveal['prevout']
    hash = prevout['hash']
    index = prevout['index']
    tx = hsd.getTxByHash(hash)
    if 'inputs' not in tx:
        print(f'Something is up with this tx: {hash}')
        print(tx)
        print('---')
        # No idea what happened here
        # Check if registered?
        return None
    return tx['inputs'][index]['prevout']['hash']


def revealAuction(account, domain):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if account_name == False:
        return {
            "error": {
                "message": "Invalid account"
            }
        }

    try:
        response = hsw.sendREVEAL(account_name, password, domain)
        return response
    except Exception as e:
        return {
            "error": str(e)
        }


def revealAll(account):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if account_name == False:
        return {
            "error": {
                "message": "Invalid account"
            }
        }

    try:
        # Try to select and login to the wallet
        response = hsw.rpc_selectWallet(account_name)
        if response['error'] is not None:
            return
        response = hsw.rpc_walletPassphrase(password, 10)
        if response['error'] is not None:
            if response['error']['message'] != "Wallet is not encrypted.":
                return {
                    "error": {
                        "message": response['error']['message']
                    }
                }

        return requests.post(get_wallet_api_url(), json={"method": "sendbatch", "params": [[["REVEAL"]]]}).json()
    except Exception as e:
        return {
            "error": {
                "message": str(e)
            }
        }


def redeemAll(account):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if account_name == False:
        return {
            "error": {
                "message": "Invalid account"
            }
        }

    try:
        # Try to select and login to the wallet
        response = hsw.rpc_selectWallet(account_name)
        if response['error'] is not None:
            return
        response = hsw.rpc_walletPassphrase(password, 10)
        if response['error'] is not None:
            if response['error']['message'] != "Wallet is not encrypted.":
                return {
                    "error": {
                        "message": response['error']['message']
                    }
                }

        return requests.post(get_wallet_api_url(), json={"method": "sendbatch", "params": [[["REDEEM"]]]}).json()
    except Exception as e:
        return {
            "error": {
                "message": str(e)
            }
        }


def registerAll(account):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if account_name == False:
        return {
            "error": {
                "message": "Invalid account"
            }
        }

    # try:
    domains = getPendingRegisters(account_name)
    if len(domains) == 0:
        return {
            "error": {
                "message": "Nothing to do."
            }
        }
    batch = []
    for domain in domains:
        batch.append(["UPDATE", domain['name'], {"records": []}])
    return sendBatch(account, batch)


def finalizeAll(account):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if account_name == False:
        return {
            "error": {
                "message": "Invalid account"
            }
        }

    return sendBatch(account, [["FINALIZE"]])


def rescan_auction(account, domain):
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
    response = hsw.rpc_importName(domain, height)
    return response


def bid(account, domain, bid, blind):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if account_name == False:
        return {
            "error": {
                "message": "Invalid account"
            }
        }

    bid = int(bid)*1000000
    lockup = int(blind)*1000000 + bid

    try:
        response = hsw.sendBID(account_name, password, domain, bid, lockup)
        return response
    except Exception as e:
        return {
            "error": {
                "message": str(e)
            }
        }


def openAuction(account, domain):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if account_name == False:
        return {
            "error": {
                "message": "Invalid account"
            }
        }

    try:
        response = hsw.sendOPEN(account_name, password, domain)
        return response
    except Exception as e:
        return {
            "error": {
                "message": str(e)
            }
        }


def transfer(account, domain, address):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if account_name == False:
        return {
            "error": {
                "message": "Invalid account"
            }
        }

    try:
        response = hsw.sendTRANSFER(account_name, password, domain, address)
        return response
    except Exception as e:
        return {
            "error": {
                "message": str(e)
            }
        }


def finalize(account, domain):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if account_name == False:
        return {
            "error": {
                "message": "Invalid account"
            }
        }

    try:
        response = hsw.rpc_selectWallet(account_name)
        if response['error'] is not None:
            return {
                "error": {
                    "message": response['error']['message']
                }
            }
        response = hsw.rpc_walletPassphrase(password, 10)
        if response['error'] is not None:
            if response['error']['message'] != "Wallet is not encrypted.":
                return {
                    "error": {
                        "message": response['error']['message']
                    }
                }
        response = hsw.rpc_sendFINALIZE(domain)
        return response
    except Exception as e:
        return {
            "error": {
                "message": str(e)
            }
        }


def cancelTransfer(account, domain):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if account_name == False:
        return {
            "error": {
                "message": "Invalid account"
            }
        }

    try:
        response = hsw.rpc_selectWallet(account_name)
        if response['error'] is not None:
            return {
                "error": {
                    "message": response['error']['message']
                }
            }
        response = hsw.rpc_walletPassphrase(password, 10)
        if response['error'] is not None:
            if response['error']['message'] != "Wallet is not encrypted.":
                return {
                    "error": {
                        "message": response['error']['message']
                    }
                }
        response = hsw.rpc_sendCANCEL(domain)
        return response
    except Exception as e:
        return {
            "error": {
                "message": str(e)
            }
        }


def revoke(account, domain):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if account_name == False:
        return {
            "error": {
                "message": "Invalid account"
            }
        }

    try:
        response = hsw.rpc_selectWallet(account_name)
        if response['error'] is not None:
            return {
                "error": {
                    "message": response['error']['message']
                }
            }
        response = hsw.rpc_walletPassphrase(password, 10)
        if response['error'] is not None:
            if response['error']['message'] != "Wallet is not encrypted.":
                return {
                    "error": {
                        "message": response['error']['message']
                    }
                }
        response = hsw.rpc_sendREVOKE(domain)
        return response
    except Exception as e:
        return {
            "error": {
                "message": str(e)
            }
        }


def sendBatch(account, batch):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if account_name == False:
        return {
            "error": {
                "message": "Invalid account"
            }
        }

    try:
        response = hsw.rpc_selectWallet(account_name)
        if response['error'] is not None:
            return {
                "error": {
                    "message": response['error']['message']
                }
            }
        response = hsw.rpc_walletPassphrase(password, 10)
        if response['error'] is not None:
            if response['error']['message'] != "Wallet is not encrypted.":
                return {
                    "error": {
                        "message": response['error']['message']
                    }
                }
        response = requests.post(get_wallet_api_url(), json={
            "method": "sendbatch",
            "params": [batch]
        }).json()
        if response['error'] is not None:
            return response
        if 'result' not in response:
            return {
                "error": {
                    "message": "No result"
                }
            }

        return response['result']
    except Exception as e:
        return {
            "error": {
                "message": str(e)
            }
        }


def createBatch(account, batch):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if account_name == False:
        return {
            "error": {
                "message": "Invalid account"
            }
        }

    try:
        response = hsw.rpc_selectWallet(account_name)
        if response['error'] is not None:
            return {
                "error": {
                    "message": response['error']['message']
                }
            }
        response = hsw.rpc_walletPassphrase(password, 10)
        if response['error'] is not None:
            if response['error']['message'] != "Wallet is not encrypted.":
                return {
                    "error": {
                        "message": response['error']['message']
                    }
                }
        response = requests.post(get_wallet_api_url(), json={
            "method": "createbatch",
            "params": [batch]
        }).json()
        if response['error'] is not None:
            return response
        if 'result' not in response:
            return {
                "error": {
                    "message": "No result"
                }
            }

        return response['result']
    except Exception as e:
        return {
            "error": {
                "message": str(e)
            }
        }


# region settingsAPIs
def rescan():
    try:
        response = hsw.walletRescan(0)
        return response
    except Exception as e:
        return {
            "error": {
                "message": str(e)
            }
        }


def resendTXs():
    try:
        response = hsw.walletResend()
        return response
    except Exception as e:
        return {
            "error": {
                "message": str(e)
            }
        }


def zapTXs(account):
    age = 60 * 20  # 20 minutes

    account_name = check_account(account)

    if account_name == False:
        return {
            "error": {
                "message": "Invalid account"
            }
        }

    try:
        response = requests.post(get_wallet_api_url(f"/wallet/{account_name}/zap"),
                                 json={"age": age,
                                       "account": "default"
                                       })
        return response
    except Exception as e:
        return {
            "error": {
                "message": str(e)
            }
        }


def getxPub(account):
    account_name = check_account(account)

    if account_name == False:
        return {
            "error": {
                "message": "Invalid account"
            }
        }

    try:
        response = hsw.getAccountInfo(account_name, "default")
        if 'error' in response:
            return {
                "error": {
                    "message": response['error']['message']
                }
            }
        return response['accountKey']

        return response
    except Exception as e:
        return {
            "error": {
                "message": str(e)
            }
        }


def signMessage(account, domain, message):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if account_name == False:
        return {
            "error": {
                "message": "Invalid account"
            }
        }

    try:
        response = hsw.rpc_selectWallet(account_name)
        if response['error'] is not None:
            return {
                "error": {
                    "message": response['error']['message']
                }
            }
        response = hsw.rpc_walletPassphrase(password, 10)
        if response['error'] is not None:
            if response['error']['message'] != "Wallet is not encrypted.":
                return {
                    "error": {
                        "message": response['error']['message']
                    }
                }
        response = hsw.rpc_signMessageWithName(domain, message)
        return response
    except Exception as e:
        return {
            "error": {
                "message": str(e)
            }
        }


def verifyMessageWithName(domain, signature, message):
    try:
        response = hsd.rpc_verifyMessageWithName(domain, signature, message)
        if 'result' in response:
            return response['result']
        return False
    except Exception as e:
        return False


def verifyMessage(address, signature, message):
    try:
        response = hsd.rpc_verifyMessage(address, signature, message)
        if 'result' in response:
            return response['result']
        return False
    except Exception as e:
        return False

# endregion


def generateReport(account, format="{name},{expiry},{value},{maxBid}"):
    domains = getDomains(account)

    lines = [format.replace("{", "").replace("}", "")]
    for domain in domains:
        line = format.replace("{name}", domain['name'])
        expiry = "N/A"
        expiryBlock = "N/A"
        if 'daysUntilExpire' in domain['stats']:
            days = domain['stats']['daysUntilExpire']
            # Convert to dateTime
            expiry = datetime.now() + timedelta(days=days)
            expiry = expiry.strftime("%d/%m/%Y %H:%M:%S")
            expiryBlock = str(domain['stats']['renewalPeriodEnd'])

        line = line.replace("{expiry}", expiry)
        line = line.replace("{state}", domain['state'])
        line = line.replace("{expiryBlock}", expiryBlock)
        line = line.replace("{value}", str(domain['value']/1000000))
        line = line.replace("{maxBid}", str(domain['highest']/1000000))
        line = line.replace("{openHeight}", str(domain['height']))
        lines.append(line)

    return lines


def convertHNS(value: int):
    return value/1000000
    return value/1000000


def get_node_api_url(path=''):
    """Construct a URL for the HSD node API."""
    base_url = f"http://x:{HSD_API}@{HSD_IP}:{HSD_NODE_PORT}"
    if path:
        # Ensure path starts with a slash if it's not empty
        if not path.startswith('/'):
            path = f'/{path}'
        return f"{base_url}{path}"
    return base_url

def get_wallet_api_url(path=''):
    """Construct a URL for the HSD wallet API."""
    base_url = f"http://x:{HSD_API}@{HSD_IP}:{HSD_WALLET_PORT}"
    if path:
        # Ensure path starts with a slash if it's not empty
        if not path.startswith('/'):
            path = f'/{path}'
        return f"{base_url}{path}"
    return base_url
