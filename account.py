from datetime import datetime, timedelta
from handywrapper import api
import os
import dotenv
import requests
import re
import domainLookup
import json
import time
import subprocess
import atexit
import signal
import sys
import threading
import sqlite3
import logging
logger = logging.getLogger("firewallet")


dotenv.load_dotenv()

HSD_API = os.getenv("HSD_API","")
HSD_IP = os.getenv("HSD_IP","localhost")

HSD_NETWORK = os.getenv("HSD_NETWORK", "main")
HSD_WALLET_PORT = 12039
HSD_NODE_PORT = 12037

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

HSD_INTERNAL_NODE = os.getenv("INTERNAL_HSD","false").lower() in ["1","true","yes"]
if HSD_INTERNAL_NODE:
    if HSD_API == "":
        # Use a random API KEY
        HSD_API = "firewallet-" + str(int(time.time()))
    HSD_IP = "localhost"

SHOW_EXPIRED = os.getenv("SHOW_EXPIRED")
if SHOW_EXPIRED is None:
    SHOW_EXPIRED = False

HSD_PROCESS = None
SPV_MODE = None

# Get hsdconfig.json
HSD_CONFIG = {
    "version": "v8.0.0",
    "chainMigrate": 4,
    "walletMigrate": 7,
    "minNodeVersion": 20,
    "minNpmVersion": 8,
    "spv": False,
    "flags": [
        "--agent=FireWallet"
    ]
}

TX_CACHE_TTL = 3600
DOMAIN_CACHE_TTL = int(os.getenv("CACHE_TTL",90))

if not os.path.exists('hsdconfig.json'):
    with open('hsdconfig.json', 'w') as f:
        f.write(json.dumps(HSD_CONFIG, indent=4))
else:
    with open('hsdconfig.json') as f:
        hsdConfigTMP = json.load(f)
        for key in hsdConfigTMP:
            HSD_CONFIG[key] = hsdConfigTMP[key]

hsd = api.hsd(HSD_API, HSD_IP, HSD_NODE_PORT)
hsw = api.hsw(HSD_API, HSD_IP, HSD_WALLET_PORT)

# Verify the connection
response = hsd.getInfo()

EXCLUDE = os.getenv("EXCLUDE","primary").split(",")


def hsdConnected():
    if hsdVersion() == -1:
        return False
    return True


def hsdVersion(format=True):
    info = hsd.getInfo()
    if 'error' in info:
        logger.error(f"HSD connection error: {info.get('error', 'Unknown error')}")
        return -1
    
    # Check if SPV mode is enabled
    global SPV_MODE
    if info.get('chain',{}).get('options',{}).get('spv',False):
        SPV_MODE = True
    else:
        SPV_MODE = False
    if format:
        return float('.'.join(info['version'].split(".")[:2]))
    else:
        return info['version']


def check_account(cookie: str | None):
    if cookie is None:
        return False

    # Check the account
    if cookie.count(":") < 1:
        return False

    account = cookie.split(":")[0]
    # Check if the account is valid
    info = hsw.getAccountInfo(account, 'default')
    if 'error' in info:
        logger.error(f"HSW error checking account {account}: {info.get('error', 'Unknown error')}")
        return False
    return account


def check_password(cookie: str|None, password: str|None):
    if cookie is None:
        return False
    if password is None:
        password = ""
    
    account = check_account(cookie)
    if not account:
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
    

def init_domain_db():
    """Initialize the SQLite database for domain cache."""
    os.makedirs('cache', exist_ok=True)
    db_path = os.path.join('cache', 'domains.db')
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create the domains table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS domains (
        name TEXT PRIMARY KEY,
        info TEXT,
        last_updated INTEGER
    )
    ''')
    
    conn.commit()
    conn.close()


def getCachedDomains():
    """Get cached domain information from SQLite database."""
    init_domain_db()  # Ensure DB exists
    
    db_path = os.path.join('cache', 'domains.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    cursor = conn.cursor()
    
    # Get all domains from the database
    cursor.execute('SELECT name, info, last_updated FROM domains')
    rows = cursor.fetchall()
    
    # Convert to dictionary format
    domain_cache = {}
    for row in rows:
        try:
            domain_cache[row['name']] = json.loads(row['info'])
            domain_cache[row['name']]['last_updated'] = row['last_updated']
        except json.JSONDecodeError:
            logger.error(f"Error parsing cached data for domain {row['name']}")
    
    conn.close()
    return domain_cache


ACTIVE_DOMAIN_UPDATES = set()  # Track domains being updated
DOMAIN_UPDATE_LOCK = threading.Lock()  # For thread-safe access to ACTIVE_DOMAIN_UPDATES

def update_domain_cache(domain_names: list):
    """Fetch domain info and update the SQLite cache."""
    if not domain_names:
        return
    
    # Filter out domains that are already being updated
    domains_to_update = []
    with DOMAIN_UPDATE_LOCK:
        for domain in domain_names:
            if domain not in ACTIVE_DOMAIN_UPDATES:
                ACTIVE_DOMAIN_UPDATES.add(domain)
                domains_to_update.append(domain)
    
    if not domains_to_update:
        # All requested domains are already being updated
        return
        
    try:
        # Initialize database
        init_domain_db()
        
        db_path = os.path.join('cache', 'domains.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        for domain_name in domains_to_update:
            try:
                # Get domain info from node
                domain_info = getDomain(domain_name)
                
                if 'error' in domain_info or not domain_info.get('info'):
                    logger.error(f"Failed to get info for domain {domain_name}: {domain_info.get('error', 'Unknown error')}")
                    continue
                
                # Update or insert into database
                now = int(time.time())
                serialized_info = json.dumps(domain_info)
                
                cursor.execute(
                    'INSERT OR REPLACE INTO domains (name, info, last_updated) VALUES (?, ?, ?)',
                    (domain_name, serialized_info, now)
                )
                
                logger.info(f"Updated cache for domain {domain_name}")
            except Exception as e:
                logger.error(f"Error updating cache for domain {domain_name}: {str(e)}", exc_info=True)
            finally:
                # Always remove from active set, even if there was an error
                with DOMAIN_UPDATE_LOCK:
                    if domain_name in ACTIVE_DOMAIN_UPDATES:
                        ACTIVE_DOMAIN_UPDATES.remove(domain_name)
        
        # Commit all changes at once
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error updating domain cache: {str(e)}", exc_info=True)
        # Make sure to clean up the active set on any exception
        with DOMAIN_UPDATE_LOCK:
            for domain in domains_to_update:
                if domain in ACTIVE_DOMAIN_UPDATES:
                    ACTIVE_DOMAIN_UPDATES.remove(domain)
    
    logger.info("Updated cache for domains")


def getBalance(account: str):
    # Get the total balance
    info = hsw.getBalance('default', account)
    if 'error' in info:
        logger.error(f"Error getting balance for account {account}: {info['error']}")
        return {'available': 0, 'total': 0}

    total = info['confirmed']
    available = total - info['lockedConfirmed']
    locked = info['lockedConfirmed'] / 1000000

    # Convert to HNS
    total = total / 1000000
    available = available / 1000000
    logger.debug(f"Initial balance for account {account}: total={total}, available={available}, locked={locked}")

    domains = getDomains(account)
    domainValue = 0
    domains_to_update = []  # Track domains that need cache updates
    
    if isSPV():
        # Initialize database if needed
        init_domain_db()
        
        # Connect to the database directly for efficient querying
        db_path = os.path.join('cache', 'domains.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        now = int(time.time())
        cache_cutoff = now - (DOMAIN_CACHE_TTL * 86400)  # Cache TTL in days
        
        for domain in domains:
            domain_name = domain['name']
            
            # Check if domain is in cache and still fresh
            cursor.execute(
                'SELECT info, last_updated FROM domains WHERE name = ?', 
                (domain_name,)
            )
            row = cursor.fetchone()
            
            # Only add domain for update if:
            # 1. Not in cache or stale
            # 2. Not currently being updated by another thread
            with DOMAIN_UPDATE_LOCK:
                if (not row or row['last_updated'] < cache_cutoff) and domain_name not in ACTIVE_DOMAIN_UPDATES:
                    domains_to_update.append(domain_name)
                    continue
                
            # Use the cached info
            try:
                if row:  # Make sure we have data
                    domain_info = json.loads(row['info'])
                    if domain_info.get('info', {}).get('state', "") == "CLOSED":
                        domainValue += domain_info.get('info', {}).get('value', 0)
            except json.JSONDecodeError:
                logger.warning(f"Error parsing cached data for domain {domain_name}")
                # Only add for update if not already being updated
                with DOMAIN_UPDATE_LOCK:
                    if domain_name not in ACTIVE_DOMAIN_UPDATES:
                        domains_to_update.append(domain_name)
        
        conn.close()
    else:
        for domain in domains:
            if domain['state'] == "CLOSED":
                domainValue += domain['value']
    
    # Start background thread to update cache for missing domains
    if domains_to_update:
        thread = threading.Thread(
            target=update_domain_cache,
            args=(domains_to_update,),
            daemon=True
        )
        thread.start()
        
    total = total - (domainValue/1000000)
    locked = locked - (domainValue/1000000)
    logger.debug(f"Adjusted balance for account {account}: total={total}, available={available}, locked={locked}")

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

def init_tx_page_db():
    """Initialize the SQLite database for transaction page cache."""
    os.makedirs('cache', exist_ok=True)
    db_path = os.path.join('cache', 'tx_pages.db')
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create the tx_pages table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tx_pages (
        account TEXT,
        page_key TEXT,
        txid TEXT,
        timestamp INTEGER,
        PRIMARY KEY (account, page_key)
    )
    ''')
    
    conn.commit()
    conn.close()

def getPageTXCache(account, page, size=100):
    """Get cached transaction ID from SQLite database."""
    account = getxPub(account)
    page_key = f"{page}-{size}"
    
    # Initialize database if needed
    init_tx_page_db()
    
    db_path = os.path.join('cache', 'tx_pages.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Query for the cached transaction ID
    cursor.execute(
        'SELECT txid, timestamp FROM tx_pages WHERE account = ? AND page_key = ?',
        (account, page_key)
    )
    row = cursor.fetchone()
    conn.close()
    
    if row and row[1] > int(time.time()) - TX_CACHE_TTL:
        return row[0]  # Return the cached txid
    return None

def pushPageTXCache(account, page, txid, size=100):
    """Store transaction ID in SQLite database."""
    account = getxPub(account)
    page_key = f"{page}-{size}"
    
    # Initialize database if needed
    init_tx_page_db()
    
    db_path = os.path.join('cache', 'tx_pages.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Insert or replace the transaction ID
    cursor.execute(
        'INSERT OR REPLACE INTO tx_pages (account, page_key, txid, timestamp) VALUES (?, ?, ?, ?)',
        (account, page_key, txid, int(time.time()))
    )
    
    conn.commit()
    conn.close()
    
    return txid

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
            logger.error(f"Error getting transactions for account {account}: {info['error']}")
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
        logger.error(f"Error fetching transactions: {response.status_code} - {response.text}")
        return []
    data = response.json()

    # Refresh the cache if the next page is different
    nextPage = getPageTXCache(account, page, limit)
    if nextPage is not None and nextPage != data[-1]['hash']:
        logger.info(f'Refreshing tx page {page}')
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

    if response['result']['isvalid']:
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
    if not address.startswith("Hip2: "):
        if not check_address(address, False, True):
            return 'Hip2: Lookup succeeded but address is invalid'
        return address

    # Check if DISABLE_WALLETDNS is set
    if os.getenv("DISABLE_WALLETDNS","").lower() in ["1","true","yes"]:
        return "No HIP2 record found for this domain"
    # Try using WALLET TXT record
    address = domainLookup.wallet_txt(domain)
    if not address.startswith("hs1"):
        return "No HIP2 or WALLET record found for this domain"
    if not check_address(address, False, True):
        return 'WALLET DNS record found but address is invalid'
    return address

    


def send(account, address, amount):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])
    if not account_name:
        return {
            "error": {
                "message": "Invalid account"
            }
        }
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
    if 'info' not in domain_info or domain_info['info'] is None:
        return False
    if 'owner' not in domain_info['info']:
        return False

    owner = getAddressFromCoin(domain_info['info']['owner'].get("hash"),domain_info['info']['owner'].get("index"))
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

def isOwnPrevout(account, prevout: dict):
    if 'hash' not in prevout or 'index' not in prevout:
        return False
    # Get the address from the prevout
    address = getAddressFromCoin(prevout['hash'], prevout['index'])
    # Select the account
    hsw.rpc_selectWallet(account)
    account = hsw.rpc_getAccount(address)

    if 'error' in account and account['error'] is not None:
        return False
    if 'result' not in account:
        return False
    if account['result'] == 'default':
        return True
    return False
    

def getDomain(domain: str):
    if isSPV():
        response = requests.get(f"https://hsd.hns.au/api/v1/name/{domain}").json()
        if 'error' in response:
            return {
                "error": {
                    "message": response['error']
                }
            }
        return response

    # Get the domain
    response = hsd.rpc_getNameInfo(domain)
    if response['error'] is not None:
        return {
            "error": {
                "message": response['error']['message']
            }
        }
    return response['result']

def isKnownDomain(domain: str) -> bool:
    # Get the domain
    response = hsd.rpc_getNameInfo(domain)
    if response['error'] is not None:
        return False
    
    if response['result'] is None or response['result'].get('info') is None:
        return False
    return True

def getAddressFromCoin(coinhash: str, coinindex = 0):
    # Get the address from the hash
    response = requests.get(get_node_api_url(f"coin/{coinhash}/{coinindex}"))
    if response.status_code != 200:
        logger.error("Error getting address from coin")
        return "No Owner"
    data = response.json()
    if 'address' not in data:
        logger.error("Error getting address from coin")
        logger.error(json.dumps(data, indent=4))
        return "No Owner"
    return data['address']


def renewDomain(account, domain):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if not account_name:
        return {
            "error": {
                "message": "Invalid account"
            }
        }

    response = hsw.sendRENEW(account_name, password, domain)
    return response


def getDNS(domain: str):
    # Get the DNS

    if isSPV():
        response = requests.get(f"https://hsd.hns.au/api/v1/nameresource/{domain}")
        if response.status_code != 200:
            return {
                "error": f"Error fetching DNS records: {response.status_code}"
            }
        response = response.json()
        return response.get('records', [])


    response = hsd.rpc_getNameResource(domain)
    if response['error'] is not None:
        return {
            "error": response['error']['message']
        }
    if 'result' not in response:
        return {
            "error": "No DNS records"
        }
    if response['result'] is None:
        return []

    if 'records' not in response['result']:
        return []
    return response['result']['records']


def setDNS(account, domain, records):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if not account_name:
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
        logger.error(f"Error getting node sync status: {response['error']}")
        return 0

    sync = response['chain']['progress']*100
    sync = round(sync, 2)
    return sync


def getWalletStatus():
    response = hsw.rpc_getWalletInfo()
    if 'error' in response and response['error'] is not None:
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
                        if reveal['own']:
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
    except Exception as e:
        logger.error(f"Failed to parse redeems: {str(e)}", exc_info=True)

    return pending


def getPendingRegisters(account):
    bids = getBids(account)
    domains = getDomains(account, False)
    pending = []
    for domain in domains:
        if domain['state'] == "CLOSED" and not domain['registered']:
            for bid in bids:
                if bid['name'] == domain['name']:
                    if bid['value'] == domain['highest']:
                        # Double check the domain is actually in the node                        
                        if isKnownDomain(domain['name']):
                            pending.append(bid)
    return pending


def getPendingFinalizes(account, password):
    tx = createBatch(f'{account}:{password}', [["FINALIZE"]])
    if 'error' in tx:
        return []

    pending = []
    try:
        for output in tx['outputs']:
            if type(output) is not dict:
                continue
            if 'covenant' not in output:
                continue
            if output['covenant'].get("type") != 10:
                continue
            if output['covenant'].get('action') != "FINALIZE":
                continue
            nameHash = output['covenant']['items'][0]
            # Try to get the name from hash
            name = hsd.rpc_getNameByHash(nameHash)
            if name['error']:
                pending.append(nameHash)
            else:
                pending.append(name['result'])
    except Exception as e:
        logger.error(f"Failed to parse finalizes: {str(e)}", exc_info=True)
    return pending


def getRevealTX(reveal):
    prevout = reveal['prevout']
    hash = prevout['hash']
    index = prevout['index']
    tx = hsd.getTxByHash(hash)
    if 'inputs' not in tx:
        logger.error(f'Something is up with this tx: {hash}')
        logger.error(tx)
        # No idea what happened here
        # Check if registered?
        return None
    return tx['inputs'][index]['prevout']['hash']


def revealAuction(account, domain):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if not account_name:
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

    if not account_name:
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

    if not account_name:
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

    if not account_name:
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

    if not account_name:
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
    if 'height' not in response['result']['info']:
        return {
            "error": "Can't find start"
        }


    height = response['result']['info']['height']-1
    response = hsw.rpc_importName(domain, height)
    return response


def bid(account, domain, bid, blind):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if not account_name:
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

    if not account_name:
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

    if not account_name:
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

    if not account_name:
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

    if not account_name:
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

    if not account_name:
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

    if not account_name:
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

    if not account_name:
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

# region Mempool
def getMempoolTxs():
    # hsd-cli rpc getrawmempool
    response = hsd.rpc_getRawMemPool()
    if 'error' in response and response['error'] is not None:
        return []

    return response['result'] if 'result' in response else []


def getMempoolBids():
    mempoolTxs = getMempoolTxs()
    bids = {}
    for txid in mempoolTxs:
        tx = hsd.getTxByHash(txid)
        if 'error' in tx and tx['error'] is not None:
            logger.error(f"Error getting tx {txid}: {tx['error']}")
            continue
        if 'outputs' not in tx:
            logger.error(f"Error getting outputs for tx {txid}")
            continue
        for output in tx['outputs']:
            if output['covenant']['action'] not in ["BID", "REVEAL"]:
                continue
            if output['covenant']['action'] == "REVEAL":
                # Try to find bid tx from inputs
                namehash = output['covenant']['items'][0]
                for txInput in tx['inputs']:
                    if txInput['coin']['covenant']['action'] != "BID":
                        continue
                    if txInput['coin']['covenant']['items'][0] != namehash:
                        continue
                    name = txInput['coin']['covenant']['items'][2]
                    # Convert name from hex to ascii
                    name = bytes.fromhex(name).decode('ascii')

                    bid = {
                        'txid': txid,
                        'lockup': txInput['coin']['value'],
                        'revealed': True,
                        'height': -1,
                        'value': output['value'],
                        'sort_value': txInput['coin']['value'],
                        'owner': "Unknown"
                    }
                    if name not in bids:
                        bids[name] = []
                    bids[name].append(bid)               
                continue

            name = output['covenant']['items'][2]
            # Convert name from hex to ascii
            name = bytes.fromhex(name).decode('ascii')
            if name not in bids:
                bids[name] = []
            bid = {
                'txid': txid,
                'value': -1000000,  # Default value if not found
                'lockup': output['value'],
                'revealed': False,
                'height': -1,
                'sort_value': output['value'],
                'owner': "Unknown"
            }
            bids[name].append(bid)
    return bids




# endregion




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


def zapTXs(account, age=1200):
    account_name = check_account(account)

    if not account_name:
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
    account_name = account
    if account.count(":") > 0:
        account_name = check_account(account)

    if not account_name:
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
    except Exception as e:
        return {
            "error": {
                "message": str(e)
            }
        }


def signMessage(account, domain, message):
    account_name = check_account(account)
    password = ":".join(account.split(":")[1:])

    if not account_name:
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
        logger.error(f"Error verifying message with name: {str(e)}", exc_info=True)
        return False


def verifyMessage(address, signature, message):
    try:
        response = hsd.rpc_verifyMessage(address, signature, message)
        if 'result' in response:
            return response['result']
        return False
    except Exception as e:
        logger.error(f"Error verifying message: {str(e)}", exc_info=True)
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

SPV_EXTERNAL_ROUTES = [
    "name",
    "coin",
    "tx",
    "block"
]

def get_node_api_url(path=''):
    """Construct a URL for the HSD node API."""
    base_url = f"http://x:{HSD_API}@{HSD_IP}:{HSD_NODE_PORT}"
    if isSPV() and any(path.startswith(route) for route in SPV_EXTERNAL_ROUTES):
        # If in SPV mode and the path is one of the external routes, use the external API
        base_url = "https://hsd.hns.au/api/v1"
        
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

def isSPV() -> bool:
    global SPV_MODE
    if SPV_MODE is None:
        info = hsd.getInfo()
        if 'error' in info:
            return False
        
        # Check if SPV mode is enabled        
        if info.get('chain',{}).get('options',{}).get('spv',False):
            SPV_MODE = True
        else:
            SPV_MODE = False
    return SPV_MODE

# region HSD Internal Node



def checkPreRequisites() -> dict[str, bool]:
    prerequisites = {
        "node": False,
        "npm": False,
        "git": False,
        "hsd": False
    }
    
    try:
        # Check if node is installed and get version
        nodeSubprocess = subprocess.run(["node", "-v"], capture_output=True, text=True,timeout=2)
        if nodeSubprocess.returncode == 0:
            major_version = int(nodeSubprocess.stdout.strip().lstrip('v').split('.')[0])
            if major_version >= HSD_CONFIG.get("minNodeVersion", 20):
                prerequisites["node"] = True
    except Exception:
        pass
    
    try:
        # Check if npm is installed
        npmSubprocess = subprocess.run(["npm", "-v"], capture_output=True, text=True,timeout=2)
        if npmSubprocess.returncode == 0:
            major_version = int(npmSubprocess.stdout.strip().split('.')[0])
            if major_version >= HSD_CONFIG.get("minNPMVersion", 8):
                prerequisites["npm"] = True
    except Exception:
        pass

    try:
        # Check if git is installed
        gitSubprocess = subprocess.run(["git", "--version"], capture_output=True, text=True,timeout=2)
        if gitSubprocess.returncode == 0:
            prerequisites["git"] = True
    except Exception:
        pass

    
    # Check if hsd is installed
    if os.path.exists("./hsd/bin/hsd"):
        prerequisites["hsd"] = True

    return prerequisites



def hsdInit():
    if not HSD_INTERNAL_NODE:
        return
    
    # Don't check prerequisites if HSD is included in a docker container
    if os.getenv("HSD_DOCKER_CONTAINER", "false").lower() == "true":
        prerequisites = {
            "node": True,
            "npm": True,
            "git": True,
            "hsd": True
        }
    else:
        prerequisites = checkPreRequisites()
    
    minNodeVersion = HSD_CONFIG.get("minNodeVersion", 20)
    minNPMVersion = HSD_CONFIG.get("minNpmVersion", 8)
    PREREQ_MESSAGES = {
        "node": f"Install Node.js from https://nodejs.org/en/download (Version >= {minNodeVersion})",
        "npm": f"Install npm (version >= {minNPMVersion}) - usually comes with Node.js",
        "git": "Install Git from https://git-scm.com/downloads"}


    # Check if all prerequisites are met (except hsd)
    if not all(prerequisites[key] for key in prerequisites if key != "hsd"):
        print("HSD Internal Node prerequisites not met:",flush=True)
        logger.error("HSD Internal Node prerequisites not met:")
        for key, value in prerequisites.items():
            if not value:
                print(f" - {key} is missing or does not meet the version requirement.",flush=True)
                logger.error(f" - {key} is missing or does not meet the version requirement.")
                if key in PREREQ_MESSAGES:
                    print(PREREQ_MESSAGES[key],flush=True)
                    logger.error(PREREQ_MESSAGES[key])
        exit(1)
        return
    
    # Check if hsd is installed
    if not prerequisites["hsd"]:
        logger.info("HSD not found, installing...")
        # If hsd folder exists, remove it
        if os.path.exists("hsd"):
            os.rmdir("hsd")

        # Clone hsd repo
        gitClone = subprocess.run(["git", "clone", "--depth", "1", "--branch", HSD_CONFIG.get("version", "latest"), "https://github.com/handshake-org/hsd.git", "hsd"], capture_output=True, text=True)
        if gitClone.returncode != 0:
            print("Failed to clone hsd repository:",flush=True)
            logger.error("Failed to clone hsd repository:")
            print(gitClone.stderr,flush=True)
            logger.error(gitClone.stderr)
            exit(1)
        logger.info("Cloned hsd repository.")
        logger.info("Installing hsd dependencies...")
        # Install hsd dependencies
        npmInstall = subprocess.run(["npm", "install"], cwd="hsd", capture_output=True, text=True)
        if npmInstall.returncode != 0:
            print("Failed to install hsd dependencies:",flush=True)
            logger.error("Failed to install hsd dependencies:")
            print(npmInstall.stderr,flush=True)
            logger.error(npmInstall.stderr)
            exit(1) 
        logger.info("Installed hsd dependencies.")
def hsdStart():
    global HSD_PROCESS
    global SPV_MODE
    if not HSD_INTERNAL_NODE:
        return

    # Check if hsd was started in the last 30 seconds
    if os.path.exists("hsd.lock"):
        lock_time = os.path.getmtime("hsd.lock")
        if time.time() - lock_time < 30:
            logger.info("HSD was started recently, skipping start.")
            return
        else:
            os.remove("hsd.lock")
    
    logger.info("Starting HSD...")
    # Create a lock file
    with open("hsd.lock", "w") as f:
        f.write(str(time.time()))
    
    # Config lookups with defaults
    chain_migrate = HSD_CONFIG.get("chainMigrate", False)
    wallet_migrate = HSD_CONFIG.get("walletMigrate", False)
    spv = HSD_CONFIG.get("spv", False)
    prefix = HSD_CONFIG.get("prefix", os.path.join(os.getcwd(), "hsd_data"))


    # Base command
    cmd = [
        "node",
        "./hsd/bin/hsd",
        f"--network={HSD_NETWORK}",
        f"--prefix={prefix}",
        f"--api-key={HSD_API}",
        "--http-host=127.0.0.1",
        "--log-console=false"
    ]

    # Conditionally add migration flags
    if chain_migrate:
        cmd.append(f"--chain-migrate={chain_migrate}")
    if wallet_migrate:
        cmd.append(f"--wallet-migrate={wallet_migrate}")
    SPV_MODE = spv
    if spv:
        cmd.append("--spv")
    
    # Add flags
    if len(HSD_CONFIG.get("flags",[])) > 0:
        for flag in HSD_CONFIG.get("flags",[]):
            cmd.append(flag)

    # Launch process
    try:
        HSD_PROCESS = subprocess.Popen(
            cmd,
            cwd=os.getcwd(),
            text=True
        )
        
        logger.info(f"HSD started with PID {HSD_PROCESS.pid}")
    except Exception as e:
        logger.error(f"Failed to start HSD: {str(e)}", exc_info=True)
        return

    atexit.register(hsdStop)

    # Handle Ctrl+C
    try:
        signal.signal(signal.SIGINT, lambda s, f: (hsdStop(), sys.exit(0)))
        signal.signal(signal.SIGTERM, lambda s, f: (hsdStop(), sys.exit(0)))
    except Exception as e:
        logger.error(f"Failed to set signal handlers: {str(e)}", exc_info=True)
        pass

def hsdRunning() -> bool:
    global HSD_PROCESS
    if not HSD_INTERNAL_NODE:
        return False
    if HSD_PROCESS is None:
        return False
    
    # Check if process has terminated
    poll_result = HSD_PROCESS.poll()
    if poll_result is not None:
        logger.error(f"HSD process has terminated with exit code: {poll_result}")
        return False
    return True

def hsdStop():
    global HSD_PROCESS

    if HSD_PROCESS is None:
        return
    
    logger.info("Stopping HSD...")

    # Send SIGINT (like Ctrl+C)
    HSD_PROCESS.send_signal(signal.SIGINT)

    try:
        HSD_PROCESS.wait(timeout=10)  # wait for graceful exit
        logger.info("HSD shut down cleanly.")
    except subprocess.TimeoutExpired:
        logger.warning("HSD did not exit yet, is it alright???")
    
    # Clean up lock file
    if os.path.exists("hsd.lock"):
        os.remove("hsd.lock")

    HSD_PROCESS = None

def hsdRestart():
    hsdStop()
    time.sleep(2)
    hsdStart()

hsdInit()
hsdStart()
# endregion