import io
import json
import random
import sqlite3
import sys
from flask import Flask, make_response, redirect, request, jsonify, render_template, send_from_directory,send_file
import os
import dotenv
import requests
import re
from flask_qrcode import QRcode
import urllib.parse
import gitinfo
import datetime
import time
import logging
from logging.handlers import RotatingFileHandler

dotenv.load_dotenv()

# Setup logging
if not os.path.exists('logs'):
    os.makedirs('logs')
log_file = 'logs/firewallet.log'
handler = RotatingFileHandler(log_file, maxBytes=1024*1024, backupCount=3)
formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger()

log_level = os.getenv("LOG_LEVEL", "WARNING").upper()
if log_level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
    logger.setLevel(getattr(logging, log_level))
else:
    logger.setLevel(logging.WARNING)

# Disable werkzeug logging
logging.getLogger('werkzeug').setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("requests").setLevel(logging.ERROR)
logger.addHandler(handler)

# Import after logger setup to capture logs from these modules
import render  # noqa: E402
import domainLookup  # noqa: E402
import account as account_module  # noqa: E402
import plugin as plugins_module  # noqa: E402

app = Flask(__name__)
qrcode = QRcode(app)

# Change this if network fees change
fees = 0.02
revokeCheck = random.randint(100000,999999)
THEME = os.getenv("THEME", "black")

@app.route('/')
def index():
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")
    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")

    
    plugins = ""
    dashFunctions = plugins_module.getDashboardFunctions()
    for function in dashFunctions:
        functionOutput = plugins_module.runPluginFunction(function["plugin"],function["function"],{},request.cookies.get("account"))
        plugins += render.plugin_output_dash(functionOutput,plugins_module.getPluginFunctionReturns(function["plugin"],function["function"]))

    # Check for updates
    if not os.path.exists(".git"):
        return render_template("index.html", account=account, plugins=plugins)
    
    alerts = get_alerts(account)
    for alert in alerts:
        output_html = alert['output']
        if 'id' in alert:
            # Add a dismiss button
            output_html += f"&nbsp<a href='/dismiss/{alert['id']}' class='btn btn-secondary btn-sm' style='margin:none;'>Dismiss</a>"
        plugins += render_template('components/dashboard-alert.html', name=alert['name'], output=output_html)

    return render_template("index.html", account=account, plugins=plugins)

def reverseDirection(direction: str):
    if direction == "⬆":
        return "⬇"
    else:
        return "⬆"


#region Transactions
# Add a cache for transactions with a timeout
tx_cache = {}
TX_CACHE_TIMEOUT = 60*5  # Cache timeout in seconds

@app.route('/tx')
def transactions():
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")
    
    # Get the page parameter
    page = request.args.get('page', 1)
    try:
        page = int(page)
    except ValueError:
        page = 1

    if page < 1:
        page = 1
    
    # Return the template with loading state - transactions will be loaded via AJAX
    return render_template("tx.html", account=account, 
                           page=page, txCount=0)
    

@app.route('/send')
def send_page():
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")
    max = account_module.getBalance(account)['available']
    # Subtract approx fee
    max = max - fees
    max = round(max, 2)

    message = ''
    address = ''
    amount = ''

    if 'message' in request.args:
        message = request.args.get("message")
    if 'address' in request.args:
        address = request.args.get("address")
    if 'amount' in request.args:
        amount = request.args.get("amount")
        

    return render_template("send.html", account=account,
                           
                           max=max,message=message,address=address,amount=amount)

@app.route('/send', methods=["POST"])
def send():
    if request.cookies.get("account") is None:
        return redirect("/login")
    
    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")
    
    # Get the address and amount
    address = request.form.get("address")
    amount = request.form.get("amount")

    if address is None or amount is None:
        return redirect(f"/send?message=Invalid address or amount&address={address}&amount={amount}")
    
    address_check = account_module.check_address(address.strip(),True,True)
    if not address_check:
        return redirect(f"/send?message=Invalid address&address={address}&amount={amount}")
    
    address = address_check
    # Check if the amount is valid
    if re.match(r"^\d+(\.\d+)?$", amount) is None:
        return redirect(f"/send?message=Invalid amount&address={address}&amount={amount}")
    
    # Check if the amount is valid
    amount = float(amount)
    if amount <= 0:
        return redirect(f"/send?message=Invalid amount&address={address}&amount={amount}")
    
    if amount > account_module.getBalance(account)['available'] - fees:
        return redirect(f"/send?message=Not enough funds to transfer&address={address}&amount={amount}")
    
    toAddress = address
    if request.form.get('address') != address:
        toAddress = f"{request.form.get('address')}<br>{address}"

    action = f"Send HNS to {request.form.get('address')}"
    content = f"Are you sure you want to send {amount} HNS to {toAddress}<br><br>"
    content += f"This will cost {amount} HNS + mining fees and is not able to be undone."

    cancel = "/send"
    confirm = f"/send/confirm?address={address}&amount={amount}"


    return render_template("confirm.html", account=account_module.check_account(request.cookies.get("account")),
                            action=action,
                            content=content,cancel=cancel,confirm=confirm)
    

@app.route('/send/confirm')
def sendConfirmed():

    address = request.args.get("address")
    amount = float(request.args.get("amount","0"))
    response = account_module.send(request.cookies.get("account"),address,amount)
    if 'error' in response and response['error'] is not None:
        # If error is a dict get the message
        if isinstance(response['error'], dict):
            if 'message' in response['error']:
                return redirect(f"/send?message={response['error']['message']}&address={address}&amount={amount}")
            else:
                return redirect(f"/send?message={response['error']}&address={address}&amount={amount}")
        
        # If error is a string
        return redirect(f"/send?message={response['error']}&address={address}&amount={amount}")
    
    return redirect(f"/success?tx={response['tx']}")
    


@app.route('/receive')
def receive():
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")
    
    address = account_module.getAddress(account)

    return render_template("receive.html", account=account,
                           
                           address=address)
    
@app.route('/success')
def success():
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")

    tx = request.args.get("tx")
    return render_template("success.html", account=account,
                           tx=tx)

@app.route('/checkaddress')
def check_address():
    address = request.args.get("address")
    if address is None:
        return jsonify({"result": "Invalid address"})
    
    return jsonify({"result": account_module.check_address(address.strip())})
#endregion

#region Domains
@app.route('/auctions')
def auctions():
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")
    
    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")


    bids = account_module.getBids(account)
    domains = account_module.getDomains(account,False)
    
    # Sort
    sort = request.args.get("sort")
    if sort is None:
        sort = "time"
    sort = sort.lower()
    sort_price = ""
    sort_price_next = "⬇"
    sort_state = ""
    sort_state_next = "⬇"
    sort_domain = ""
    sort_domain_next = "⬇"
    sort_time = ""
    sort_time_next = "⬇"
    reverse = False

    direction = request.args.get("direction")
    if direction is None:
        if sort == "time":
            direction = "⬆"
        else:
            direction = "⬇"

    if direction == "⬆":
        reverse = True

    sortbyDomain = False

    if sort == "price":
        # Sort by price
        bids = sorted(bids, key=lambda k: k['value'],reverse=reverse)
        sort_price = direction
        sort_price_next = reverseDirection(direction)
    elif sort == "state":
        sort_state = direction
        sort_state_next = reverseDirection(direction)
        domains = sorted(domains, key=lambda k: k['state'],reverse=reverse)
        sortbyDomain = True
    elif sort == "time":
        sort_time = direction
        sort_time_next = reverseDirection(direction)

        # If older HSD version sort by domain height
        if len(bids) > 0:
            if bids[0]['height'] == 0:
                domains = sorted(domains, key=lambda k: k['height'],reverse=reverse)
                sortbyDomain = True
            else:
                bids = sorted(bids, key=lambda k: k['height'],reverse=reverse)
    else:
        # Sort by domain
        bids = sorted(bids, key=lambda k: k['name'],reverse=reverse)
        sort_domain = direction
        sort_domain_next = reverseDirection(direction)
    
    bidsHtml = render.bidDomains(bids,domains,sortbyDomain)
    plugins = ""
    message = ''
    if 'message' in request.args:
        message = request.args.get("message")
    return render_template("auctions.html", account=account, domains=bidsHtml,
                           domainsMobile=bidsHtml, plugins=plugins,
                           domain_count=bidsHtml,sort_price=sort_price,
                           sort_state=sort_state,sort_domain=sort_domain,
                           sort_price_next=sort_price_next,
                           sort_state_next=sort_state_next,sort_domain_next=sort_domain_next,
                           bids=len(bids),message=message,
                           sort_time=sort_time,sort_time_next=sort_time_next)


#region All Auctions
@app.route('/reveal')
@app.route('/all/reveal')
def revealAllBids():
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")
    
    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")

    response = account_module.revealAll(request.cookies.get("account"))
    if not response:
        return redirect("/auctions?message=Failed to reveal bids")

    if 'error' in response:
        if response['error'] is not None:
            if response['error']['message'] == "Nothing to do.":
                return redirect("/auctions?message=No reveals pending")
            return redirect("/auctions?message=" + response['error']['message'])
            
    return redirect("/success?tx=" + response['result']['hash'])


@app.route('/all/redeem')
def redeemAllBids():
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")

    response = account_module.redeemAll(request.cookies.get("account"))
    if not response:
        return redirect("/auctions?message=Failed to redeem bids")

    if 'error' in response:
        if response['error'] is not None:
            if response['error']['message'] == "Nothing to do.":
                return redirect("/auctions?message=No redeems pending")
            return redirect("/auctions?message=" + response['error']['message'])
            
    return redirect("/success?tx=" + response['result']['hash'])

@app.route('/all/register')
def registerAllDomains():
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")

    response = account_module.registerAll(request.cookies.get("account"))
    if not response:
        return redirect("/auctions?message=Failed to register domains")

    if 'error' in response:
        if response['error'] is not None:
            if response['error']['message'] == "Nothing to do.":
                return redirect("/auctions?message=No domains to register")
            return redirect("/auctions?message=" + response['error']['message'])
            
    return redirect(f"/success?tx={response['hash']}")

@app.route('/all/finalize')
def finalizeAllBids():
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")

    response = account_module.finalizeAll(request.cookies.get("account"))
    if 'error' in response:
        if response['error'] is not None:
            if response['error']['message'] == "Nothing to do.":
                return redirect("/dashboard?message=No domains to finalize")
            return redirect("/dashboard?message=" + response['error']['message'])
        
    return redirect(f"/success?tx={response['hash']}")
#endregion

@app.route('/search')
def search():
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")
    
    search_term = request.args.get("q")
    if search_term is None:
        return redirect("/")
    search_term = search_term.lower().strip()

    # Replace spaces with hyphens
    search_term = search_term.replace(" ","-")
    
    # Convert emoji to punycode
    search_term = domainLookup.emoji_to_punycode(search_term)
    if len(search_term) == 0:
        return redirect("/")

    domain = account_module.getDomain(search_term)
    
    plugins = "<div class='container-fluid'>"
    # Execute domain plugins
    searchFunctions = plugins_module.getSearchFunctions()
    for function in searchFunctions:
        functionOutput = plugins_module.runPluginFunction(function["plugin"],function["function"],{"domain":search_term},account)
        plugins += render.plugin_output(functionOutput,plugins_module.getPluginFunctionReturns(function["plugin"],function["function"]))

    plugins += "</div>"

    if 'error' in domain:
        return render_template("search.html", account=account,
                               rendered=renderDomain(search_term),
                               search_term=search_term, domain=domain['error'],plugins=plugins)
    
    if domain['info'] is None:
        return render_template("search.html", account=account, 
                               rendered=renderDomain(search_term),
                               search_term=search_term,domain=search_term,
                               state="AVAILABLE", next="Available Now",plugins=plugins)

    state = domain['info']['state']
    stats = domain['info']['stats']
    next = ""
    if state == 'CLOSED':
        if domain['info']['registered']:
            state = 'REGISTERED'
            expires = stats['daysUntilExpire']
            next = f"Expires in ~{expires} days"
        else:
            state = 'AVAILABLE'
            next = "Available Now"
    elif state == "REVOKED":
            next = "Available Now"
    elif state == 'OPENING':
        next = f"Bidding opens in {str(stats['blocksUntilBidding'])} blocks (~{blocks_to_time(stats['blocksUntilBidding'])})"
    elif state == 'BIDDING':
        next = f"Reveal in {str(stats['blocksUntilReveal'])} blocks (~{blocks_to_time(stats['blocksUntilReveal'])})"
    elif state == 'REVEAL':
        next = f"Reveal ends in {str(stats['blocksUntilClose'])} blocks (~{blocks_to_time(stats['blocksUntilClose'])})"



    domain_info = account_module.getDomain(search_term)
    owner = 'Unknown'
    dns = []

    if domain_info:
        # Check if info and info.owner
        if 'info' in domain_info and 'owner' in domain_info['info']:
            owner = account_module.getAddressFromCoin(domain_info['info']['owner']['hash'],domain_info['info']['owner']['index'])
    
    dns = account_module.getDNS(search_term)

    own_domains = account_module.getDomains(account)
    own_domains = [x['name'] for x in own_domains]
    own_domains = [x.lower() for x in own_domains]
    if search_term in own_domains:
        owner = "You"

    dns = render.dns(dns)

    return render_template("search.html", account=account, 
                           rendered=renderDomain(search_term),
                           search_term=search_term,domain=domain['info']['name'],
                           raw=domain,state=state, next=next, owner=owner,
                           dns=dns,plugins=plugins)
    
@app.route('/manage/<domain>')
def manage(domain: str):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")
    
    domain = domain.lower()

    if not account_module.isOwnDomain(account, domain):
        return redirect("/search?q=" + domain)
    
    domain_info = account_module.getDomain(domain)
    if 'error' in domain_info:
        return render_template("manage.html", account=account, 
                               rendered=renderDomain(domain),
                               domain=domain, error=domain_info['error'])
    
    if domain_info['info'] is not None and 'stats' in domain_info['info'] and 'daysUntilExpire' in domain_info['info']['stats']:
        expiry = domain_info['info']['stats']['daysUntilExpire']
    else:
        expiry = "Unknown"
    dns = account_module.getDNS(domain)
    raw_dns = str(dns).replace("'",'"')
    dns = render.dns(dns)

    errorMessage = request.args.get("error")
    if errorMessage is None:
        errorMessage = ""
    address = request.args.get("address")
    if address is None:
        address = ""
    
    finalize_time = ""
    # Check if the domain is in transfer
    if domain_info['info']['transfer'] != 0:
        current_block = account_module.getBlockHeight()
        finalize_valid = domain_info['info']['transfer']+288
        finalize_blocks = finalize_valid - current_block
        if finalize_blocks > 0:
            finalize_time = "in "+ str(finalize_blocks) + " blocks (~" + str(round(finalize_blocks/6)) + " hours)"
        else:
            finalize_time = "now"

    plugins = "<div class='container-fluid'>"
    # Execute domain plugins
    domainFunctions = plugins_module.getDomainFunctions()
    for function in domainFunctions:
        functionOutput = plugins_module.runPluginFunction(function["plugin"],function["function"],{"domain":domain},account)
        plugins += render.plugin_output(functionOutput,plugins_module.getPluginFunctionReturns(function["plugin"],function["function"]))

    plugins += "</div>"


    return render_template("manage.html", account=account, 
                           rendered=renderDomain(domain),
                           error=errorMessage, address=address,
                           domain=domain,expiry=expiry, dns=dns,
                           raw_dns=urllib.parse.quote(raw_dns),
                           finalize_time=finalize_time,plugins=plugins)


@app.route('/manage/<domain>/finalize')
def finalize(domain: str):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    
    if not account_module.check_account(request.cookies.get("account")):
        return redirect("/logout")
    
    domain = domain.lower()
    response = account_module.finalize(request.cookies.get("account"),domain)
    if response['error'] is not None:
        logger.error(f"Error finalizing transfer for {domain}: {response['error']}")
        return redirect("/manage/" + domain + "?error=" + response['error']['message'])

    return redirect("/success?tx=" + response['result']['hash'])

@app.route('/manage/<domain>/cancel')
def cancelTransfer(domain: str):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    
    if not account_module.check_account(request.cookies.get("account")):
        return redirect("/logout")
    
    domain = domain.lower()
    response = account_module.cancelTransfer(request.cookies.get("account"),domain)
    if 'error' in response:
        if response['error'] is not None:
            logger.error(f"Error canceling transfer for {domain}: {response['error']}")
            return redirect("/manage/" + domain + "?error=" + response['error']['message'])

    return redirect("/success?tx=" + response['result']['hash'])

@app.route('/manage/<domain>/revoke')
def revokeInit(domain: str):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    
    if not account_module.check_account(request.cookies.get("account")):
        return redirect("/logout")
    
    domain = domain.lower()

    content = f"Are you sure you want to revoke {domain}/?<br>"
    content += "This will return the domain to the auction pool and you will lose any funds spent on the domain.<br>"
    content += "This cannot be undone after the transaction is sent.<br><br>"
    content += "Please enter your password to confirm."

    cancel = f"/manage/{domain}"
    confirm = f"/manage/{domain}/revoke/confirm"
    action = f"Revoke {domain}/"   

    
    return render_template("confirm-password.html", account=account_module.check_account(request.cookies.get("account")),
                            
                            action=action,
                            content=content,cancel=cancel,confirm=confirm,check=revokeCheck)

@app.route('/manage/<domain>/revoke/confirm', methods=["POST"])
def revokeConfirm(domain: str):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    
    if not account_module.check_account(request.cookies.get("account")):
        return redirect("/logout")
    
    domain = domain.lower()
    password = request.form.get("password")
    check = request.form.get("check")
    if check != str(revokeCheck):
        return redirect("/manage/" + domain + "?error=An error occurred. Please try again.")

    response = account_module.check_password(request.cookies.get("account"),password)
    if not response:
        return redirect("/manage/" + domain + "?error=Invalid password")


    response = account_module.revoke(request.cookies.get("account"),domain)
    if 'error' in response:
        if response['error'] is not None:
            logger.error(f"Error revoking {domain}: {response['error']}")
            return redirect("/manage/" + domain + "?error=" + response['error']['message'])

    return redirect(f"/success?tx={response['hash']}")

@app.route('/manage/<domain>/renew')
def renew(domain: str):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    
    if not account_module.check_account(request.cookies.get("account")):
        return redirect("/logout")
    
    domain = domain.lower()
    response = account_module.renewDomain(request.cookies.get("account"),domain)
    return redirect(f"/success?tx={response['hash']}")

@app.route('/manage/<domain>/edit')
def editPage(domain: str):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")
    
    domain = domain.lower()
    
    own_domains = account_module.getDomains(account)
    own_domains = [x['name'] for x in own_domains]
    own_domains = [x.lower() for x in own_domains]
    if domain not in own_domains:
        return redirect("/search?q=" + domain)
       

    user_edits = request.args.get("dns")
    if user_edits is not None:
        dns = urllib.parse.unquote(user_edits)
    else:
        dns = account_module.getDNS(domain)

    if dns and isinstance(dns, str):
        dns = json.loads(dns)
    else:
        dns = []

    # Check if new records have been added
    dnsType = request.args.get("type")
    dnsValue = request.args.get("value")
    if dnsType is not None and dnsValue is not None:
        if dnsType != "DS":
            dns.append({"type": dnsType, "value": dnsValue})
        else:
            # Verify the DS record
            ds = dnsValue.split(" ")
            if len(ds) != 4:
                raw_dns = str(dns).replace("'",'"')
                return redirect("/manage/" + domain + "/edit?dns=" + urllib.parse.quote(str(raw_dns)) + "&error=Invalid DS record")
            
            try:
                key_tag = int(ds[0])
                algorithm = int(ds[1])
                digest_type = int(ds[2])
            except ValueError:
                raw_dns = str(dns).replace("'",'"')
                return redirect("/manage/" + domain + "/edit?dns=" + urllib.parse.quote(str(raw_dns)) + "&error=Invalid DS record")
            
            dns.append({"type": dnsType, "keyTag": key_tag, "algorithm": algorithm, "digestType": digest_type, "digest": ds[3]})

        dns = json.dumps(dns).replace("'",'"')
        return redirect("/manage/" + domain + "/edit?dns=" + urllib.parse.quote(dns))

    raw_dns = str(dns).replace("'",'"')
    dns = render.dns(dns,True)
    errorMessage = request.args.get("error")
    if errorMessage is None:
        errorMessage = ""

    
    return render_template("edit.html", account=account, 
                           rendered=renderDomain(domain),
                           domain=domain, error=errorMessage,
                           dns=dns,raw_dns=urllib.parse.quote(raw_dns))


@app.route('/manage/<domain>/edit/save')
def editSave(domain: str):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    
    if not account_module.check_account(request.cookies.get("account")):
        return redirect("/logout")
    
    domain = domain.lower()
    dns = request.args.get("dns")
    if dns is None:
        return redirect(f"/manage/{domain}/edit?error=No DNS records provided")
    raw_dns = dns
    dns = urllib.parse.unquote(dns)
    response = account_module.setDNS(request.cookies.get("account"),domain,dns)
    if 'error' in response:
        logger.error(f"Error setting DNS for {domain}: {response['error']}")
        return redirect(f"/manage/{domain}/edit?dns={raw_dns}&error={response['error']}")
    return redirect(f"/success?tx={response['hash']}")

@app.route('/manage/<domain>/transfer')
def transfer(domain):
    if request.cookies.get("account") is None:
        return redirect("/login")
    
    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")
    
    # Get the address and amount
    address = request.args.get("address")

    if address is None:
        return redirect("/manage/" + domain + "?error=Invalid address")
    
    address_check = account_module.check_address(address,True,True)
    if not address_check:
        return redirect("/manage/" + domain + "?error=Invalid address")
    
    address = address_check
        
    toAddress = address
    if request.form.get('address') != address:
        toAddress = f"{request.args.get('address')}<br>{address}"

    action = f"Send {domain}/ to {request.form.get('address')}"
    content = f"Are you sure you want to send {domain}/ to {toAddress}<br><br>"
    content += "This requires sending a finalize transaction 2 days after the transfer is initiated."

    cancel = f"/manage/{domain}?address={address}"
    confirm = f"/manage/{domain}/transfer/confirm?address={address}"


    return render_template("confirm.html", account=account,action=action,
                            content=content,cancel=cancel,confirm=confirm)

@app.route('/manage/<domain>/sign')
def signMessage(domain):
    if request.cookies.get("account") is None:
        return redirect("/login")
    
    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")
    
    # Get the address and amount
    message = request.args.get("message")

    if message is None:
        return redirect("/manage/" + domain + "?error=Invalid message")
    

    content = "Message to sign:<br><code>" + message + "</code><br><br>"
    signedMessage = account_module.signMessage(request.cookies.get("account"),domain,message)
    if signedMessage["error"] is not None:
        return redirect("/manage/" + domain + "?error=" + signedMessage["error"])
    content += f"Signature:<br><code>{signedMessage['result']}</code><br><br>"

    data = {
        "domain": domain,
        "message": message,
        "signature": signedMessage["result"]
    }

    content += "Full information:<br><code style='text-align:left;display: block;'>" + json.dumps(data,indent=4).replace('\n',"<br>") + "</code><br><br>"

    content += "<textarea style='display: none;' id='data' rows='4' cols='50'>"+json.dumps(data)+"</textarea>"

    copyScript = "<script>function copyToClipboard() {var copyText = document.getElementById('data');copyText.style.display = 'block';copyText.select();copyText.setSelectionRange(0, 99999);document.execCommand('copy');copyText.style.display = 'none';var copyButton = document.getElementById('copyButton');copyButton.innerHTML='Copied';}</script>"
    content += "<button id='copyButton' onclick='copyToClipboard()' class='btn btn-secondary'>Copy to clipboard</button>" + copyScript

    

    return render_template("message.html", account=account,                           
                               title="Sign Message",content=content)
    

@app.route('/manage/<domain>/transfer/confirm')
def transferConfirm(domain):
    if request.cookies.get("account") is None:
        return redirect("/login")
    
    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")
    
    # Get the address and amount
    address = request.args.get("address")
    response = account_module.transfer(request.cookies.get("account"),domain,address)
    if 'error' in response:
        return redirect("/manage/" + domain + "?error=" + response['error'])
    
    return redirect(f"/success?tx={response['hash']}")

@app.route('/auction/<domain>')
def auction(domain):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")
    
    search_term = domain.lower().strip()    
    # Convert emoji to punycode
    search_term = domainLookup.emoji_to_punycode(search_term)
    if len(search_term) == 0:
        return redirect("/")

    domainInfo = account_module.getDomain(search_term)
    error = request.args.get("error")
    if error is None:
        error = ""
    
    if 'error' in domainInfo:
        return render_template("auction.html", account=account,
                               rendered=renderDomain(search_term),
                               search_term=search_term, domain=domainInfo['error'],
                               error=error)
    
    if domainInfo['info'] is None:
        if 'registered' in domainInfo and not domainInfo['registered'] and 'expired' in domainInfo and not domainInfo['expired']:
            # Needs to be registered
                next_action = 'ERROR GETTING NEXT STATE'
        else:
            next_action = f'<a href="/auction/{domain}/open">Open Auction</a>'
        return render_template("auction.html", account=account, 
                               rendered=renderDomain(search_term),
                                search_term=search_term,domain=search_term,next_action=next_action,
                               state="AVAILABLE", next="Open Auction",
                               error=error)

    state = domainInfo['info']['state']
    next_action = ''
    next = ""

    bids = []
    stats = domainInfo['info']['stats'] if 'stats' in domainInfo['info'] else {}
    if state == 'CLOSED':
        if not domainInfo['info']['registered']:
            if account_module.isOwnDomain(account,domain):
                state = 'PENDING REGISTER'
                next = "Pending Register"
                next_action = f'<a href="/auction/{domain}/register">Register Domain</a>'
            
            else:
                state = 'AVAILABLE'
                next = "Available Now"
                next_action = f'<a href="/auction/{domain}/open">Open Auction</a>'
        else:
            state = 'REGISTERED'
            expires = domainInfo['info']['stats']['daysUntilExpire']
            next = f"Expires in ~{expires} days"

            if account_module.isOwnDomain(account,domain):
                next_action = f'<a href="/manage/{domain}">Manage</a>'
    elif state == "REVOKED":
        next = "Available Now"
        next_action = f'<a href="/auction/{domain}/open">Open Auction</a>'
    elif state == 'OPENING':
        next = f"Bidding opens in {str(stats['blocksUntilBidding'])} blocks (~{blocks_to_time(stats['blocksUntilBidding'])})"
    elif state == 'BIDDING':
        next = f"Reveal in {stats['blocksUntilReveal']} blocks (~{blocks_to_time(stats['blocksUntilReveal'])})"
        if stats['blocksUntilReveal'] == 1:
            next += "<br>Bidding no longer possible"
        elif stats['blocksUntilReveal'] == 2:
            next += "<br>LAST CHANCE TO BID"
        elif stats['blocksUntilReveal'] == 3:
            next += "<br>Next block is last chance to bid"
        elif stats['blocksUntilReveal'] < 6:
            next += f"<br>Last chance to bid in {stats['blocksUntilReveal']-2} blocks"


    elif state == 'REVEAL':
        next = f"Reveal ends in {str(stats['blocksUntilClose'])} blocks (~{blocks_to_time(stats['blocksUntilClose'])})"
        next_action = f'<a href="/auction/{domain}/reveal">Reveal All</a>'

    message = ''
    if 'message' in request.args:
        message = request.args.get("message")


    return render_template("auction.html", account=account, 
                           rendered=renderDomain(search_term),
                           search_term=search_term,domain=domainInfo['info']['name'],
                           raw=domainInfo,state=state, next=next,
                           next_action=next_action, bids=bids,error=message)

@app.route('/auction/<domain>/scan')
def rescan_auction(domain):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")
    
    domain = domain.lower()
    
    account_module.rescan_auction(account,domain)
    return redirect("/auction/" + domain)

@app.route('/auction/<domain>/bid')
def bid(domain):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    
    if not account_module.check_account(request.cookies.get("account")):
        return redirect("/logout")
    
    domain = domain.lower()
    bid = request.args.get("bid","")
    blind = request.args.get("blind","")

    if bid == "":
        bid = 0
    if blind == "":
        blind = 0

    bid = float(bid)
    blind = float(blind)

    if bid+blind == 0:
        return redirect("/auction/" + domain+ "?error=Invalid bid amount")

    
    # Show confirm page
    total = bid + blind

    action = f"Bid on {domain}/"
    content = f"Are you sure you want to bid on {domain}/?"
    content += "You are about to bid with the following details:<br><br>"
    content += f"Bid: {str(bid)} HNS<br>"
    content += f"Blind: {str(blind)} HNS<br>"
    content += f"Total: {total} HNS (excluding fees)<br><br>"

    cancel = f"/auction/{domain}"
    confirm = f"/auction/{domain}/bid/confirm?bid={request.args.get('bid')}&blind={request.args.get('blind')}"



    return render_template("confirm.html", account=account_module.check_account(request.cookies.get("account")),
                            
                            action=action,
                            domain=domain,content=content,cancel=cancel,confirm=confirm)

@app.route('/auction/<domain>/bid/confirm')
def bid_confirm(domain):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    
    if not account_module.check_account(request.cookies.get("account")):
        return redirect("/logout")
    
    domain = domain.lower()
    bid = request.args.get("bid","")
    blind = request.args.get("blind","")

    if bid == "":
        bid = 0
    if blind == "":
        blind = 0

    bid = float(bid)
    blind = float(blind)

    
    # Send the bid
    response = account_module.bid(request.cookies.get("account"),domain,
                                  float(bid),
                                  float(blind))

    if 'error' in response:
        return redirect("/auction/" + domain + "?error=" + response['error']['message'])
    
    return redirect(f"/success?tx={response['hash']}")

@app.route('/auction/<domain>/open')
def open_auction(domain):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    
    if not account_module.check_account(request.cookies.get("account")):
        return redirect("/logout")
    
    domain = domain.lower()
    response = account_module.openAuction(request.cookies.get("account"),domain)

    if 'error' in response:
        if response['error'] is not None:
            return redirect("/auction/" + domain + "?error=" + response['error']['message'])

    return redirect(f"/success?tx={response['hash']}")

@app.route('/auction/<domain>/reveal')
def reveal_auction(domain):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    
    if not account_module.check_account(request.cookies.get("account")):
        return redirect("/logout")
    
    domain = domain.lower()
    response = account_module.revealAuction(request.cookies.get("account"),domain)
    if 'error' in response:
        return redirect(f"/auction/{domain}?message={response['error']}")
    return redirect(f"/success?tx={response['hash']}")

@app.route('/auction/<domain>/register')
def registerdomain(domain):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")
    
    if not account_module.check_account(request.cookies.get("account")):
        return redirect("/logout")
    
    domain = domain.lower()
    response = account_module.register(request.cookies.get("account"),domain)
    if 'error' in response:
        return redirect("/auction/" + domain + "?message=" + response['error']['message'])
    return redirect(f"/success?tx={response['hash']}")

#endregion
#region Settings
@app.route('/settings')
def settings():
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")
    
    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")
    
    error = request.args.get("error")
    if error is None:
        error = ""
    success = request.args.get("success")
    if success is None:
        success = ""


    if not os.path.exists(".git"):
        return render_template("settings.html", account=account,
                               hsd_version=account_module.hsdVersion(False),
                               error=error,success=success,version="Error",
                               internal=account_module.HSD_INTERNAL_NODE,
                               spv=account_module.isSPV())
    info = gitinfo.get_git_info()
    if not info:
        return render_template("settings.html", account=account,                               
                               hsd_version=account_module.hsdVersion(False),
                               error=error,success=success,version="Error",
                               internal=account_module.HSD_INTERNAL_NODE,
                               spv=account_module.isSPV())

    branch = info['refs']
    if branch != "main":
        branch = f"({branch})"
    else:
        branch = ""
    last_commit = info['author_date']
    # import to time from format "2024-02-13 11:24:03"
    last_commit = datetime.datetime.strptime(last_commit, "%Y-%m-%d %H:%M:%S")
    version = f'{last_commit.strftime("%y-%m-%d")} {branch}'
    if info['commit'] != latestVersion(info['refs']):
        version += ' (New version available)'
    return render_template("settings.html", account=account,                           
                           hsd_version=account_module.hsdVersion(False),
                           error=error,success=success,version=version,internal=account_module.HSD_INTERNAL_NODE,
                           spv=account_module.isSPV())

@app.route('/settings/<action>')
def settings_action(action):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")
    
    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")

    if action == "rescan":
        resp = account_module.rescan()
        if 'error' in resp:
            return redirect("/settings?error=" + str(resp['error']))
        return redirect("/settings?success=Rescan started")
    
    if action == "resend":
        resp = account_module.resendTXs()
        if 'error' in resp:
            return redirect("/settings?error=" + str(resp['error']))
        return redirect("/settings?success=Resent transactions")


    if action == "zap":
        age = request.args.get("age", 1200)
        try:
            age = int(age)
        except ValueError:
            age = 1200
        if age < 0:
            age = 1200
        
        resp = account_module.zapTXs(request.cookies.get("account"),age)
        if type(resp) is dict and 'error' in resp:
            return redirect("/settings?error=" + str(resp['error']))
        return redirect("/settings?success=Zapped transactions")
    
    if action == "xpub":
        xpub = account_module.getxPub(request.cookies.get("account"))
        content = "<br><br>"
        content += f"<textarea style='display: none;' id='data' rows='4' cols='50'>{xpub}</textarea>"
        content += "<script>function copyToClipboard() {var copyText = document.getElementById('data');copyText.style.display = 'block';copyText.select();copyText.setSelectionRange(0, 99999);document.execCommand('copy');copyText.style.display = 'none';var copyButton = document.getElementById('copyButton');copyButton.innerHTML='Copied';}</script>"
        content += "<button id='copyButton' onclick='copyToClipboard()' class='btn btn-secondary'>Copy to clipboard</button>"

        return render_template("message.html", account=account,
                               title="xPub Key",
                               content=f"<code>{xpub}</code>{content}")

    if action == "restart":
        resp = account_module.hsdRestart()
        return render_template("message.html", account=account,
                               title="Restarting",
                               content="The node is restarting. This may take a minute or two. You can close this window.")
    
    if action == "api-info":
        content = f"API URL: <code>http://{account_module.HSD_IP}:{account_module.HSD_NODE_PORT}</code><br>"
        content += f"Wallet URL: <code>http://{account_module.HSD_IP}:{account_module.HSD_WALLET_PORT}</code><br>"
        content += f"API Key: <code>{account_module.HSD_API}</code><br><br>"

        

        return render_template("message.html", account=account,
                               title="API Information",
                               content=content)

    if action == "logs":
        if not os.path.exists(log_file):
            return redirect("/settings?error=No log file found")
        # Check if log file is empty
        if os.path.getsize(log_file) == 0:
            return redirect("/settings?error=Log file is empty")

        try:
            with open(log_file, 'rb') as f:
                response = requests.put(f"https://upload.woodburn.au/{os.path.basename(log_file)}", data=f,
                                        headers={"Max-Days": "5"})
            if response.status_code == 200 or response.status_code == 201:
                token = response.text.strip().split('\n')[-1].split('/')[-2:]
                url = f"https://upload.woodburn.au/inline/{token[0]}/{token[1]}"
                logger.info(f"Log upload successful: {url}")                
                return redirect(url)
            else:
                logger.error(f"Failed to upload log: {response.status_code} {response.text}")
                return redirect(f"/settings?error=Failed to upload log: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Exception during log upload: {e}", exc_info=True)
            return redirect("/settings?error=An error occurred during log upload")
            


    logger.warning(f"Unknown settings action: {action}")
    return redirect("/settings?error=Invalid action")

@app.route('/settings/upload', methods=['POST'])
def upload_image():
    if 'account' not in request.cookies:
        return redirect("/login?message=Not logged in")
    
    account = request.cookies.get("account")
    account = account_module.check_account(account)
    if not account:
        return redirect("/logout")

    if not os.path.exists('user_data/images'):
        os.mkdir('user_data/images')

    if 'image' not in request.files:
        return redirect("/settings?error=No file selected")
    file = request.files['image']
    if file.filename == '':
        return redirect("/settings?error=No file selected")
    if file and file.filename:
        filepath = os.path.join(f'user_data/images/{account}.{file.filename.split(".")[-1]}')
        file.save(filepath)
        return redirect("/settings?success=File uploaded successfully")
    
    return redirect("/settings?error=An error occurred")

def latestVersion(branch):
    result = requests.get("https://git.woodburn.au/api/v1/repos/nathanwoodburn/firewalletbrowser/branches")
    if result.status_code != 200:
        return "Error"
    
    data = result.json()
    for b in data:
        if b['name'] == branch:
            return b['commit']['id']
    return "Invalid branch"

#endregion


#region Account
@app.route('/login')
def login():
    wallets = account_module.listWallets()
    wallets = render.wallets(wallets)

    # If there are no wallets redirect to either register or import
    if len(wallets) == 0:
        return redirect("/welcome")

    if 'message' in request.args:
        return render_template("login.html", 
                               error=request.args.get("message"),wallets=wallets)

    return render_template("login.html", 
                           
                           wallets=wallets)

@app.route('/login', methods=["POST"])
def login_post():
    # Get the account and password
    account = request.form.get("account")
    password = request.form.get("password")

    if account is None or password is None:
        wallets = account_module.listWallets()
        wallets = render.wallets(wallets)
        return render_template("login.html",
                               error="Invalid account or password",wallets=wallets)

    # Check if the account is valid
    if account.count(":") > 0:
        wallets = account_module.listWallets()
        wallets = render.wallets(wallets)
        return render_template("login.html",
                               error="Invalid account",wallets=wallets)

    account = account + ":" + password

    # Check if the account is valid
    if not account_module.check_password(account,password):
        wallets = account_module.listWallets()
        wallets = render.wallets(wallets)
        return render_template("login.html", 
                               error="Invalid account or password",wallets=wallets)
    # Set the cookie
    response = make_response(redirect("/"))
    response.set_cookie("account", account)
    return response

@app.route('/logout')
def logout():
    response = make_response(redirect("/login"))
    response.set_cookie("account", "", expires=0)
    return response

@app.route('/register', methods=["POST"])
def register():
    # Get the account and password
    account = request.form.get("name")
    password = request.form.get("password")
    repeatPassword = request.form.get("password_repeat")

    if account is None or password is None or repeatPassword is None:
        return render_template("register.html",
                               error="Invalid account or password",
                               name=account,password=password,password_repeat=repeatPassword)

    # Check if the passwords match
    if password != repeatPassword:
        return render_template("register.html",
                               error="Passwords do not match",
                               name=account,password=password,password_repeat=repeatPassword)

    # Check if the account is valid
    if account.count(":") > 0:
        return render_template("register.html",
                               error="Invalid account",
                               name=account,password=password,password_repeat=repeatPassword)

    # List wallets
    wallets = account_module.listWallets()
    if account in wallets:
        return render_template("register.html",
                               error="Account already exists",
                               name=account,password=password,password_repeat=repeatPassword)

    # Create the account
    response = account_module.createWallet(account,password)

    if 'error' in response:
        return render_template("register.html",
                               error=response['error'],
                               name=account,password=password,password_repeat=repeatPassword)
    
    
    # Set the cookie
    response = make_response(render_template("message.html",title="Account Created",
                                              content=f"Your account has been created. Here is your seed phrase. Please write it down and keep it safe as it will not be shown again<br><br>{response['seed']}"))
    response.set_cookie("account", account+":"+password)
    return response

@app.route('/import-wallet', methods=["POST"])
def import_wallet():
    # Get the account and password
    account = request.form.get("name")
    password = request.form.get("password")
    repeatPassword = request.form.get("password_repeat")
    seed = request.form.get("seed")

    if account is None or password is None or repeatPassword is None or seed is None:
        return render_template("import-wallet.html",
                               error="Invalid account, password or seed",
                               name=account,password=password,password_repeat=repeatPassword,
                               seed=seed)
    
    # Check if the passwords match
    if password != repeatPassword:
        return render_template("import-wallet.html",
                               error="Passwords do not match",
                               name=account,password=password,password_repeat=repeatPassword,
                               seed=seed)

    # Check if the account is valid
    if account.count(":") > 0:
        return render_template("import-wallet.html",
                               error="Invalid account",
                               name=account,password=password,password_repeat=repeatPassword,
                               seed=seed)

    # List wallets
    wallets = account_module.listWallets()
    if account in wallets:
        return render_template("import-wallet.html",
                               error="Account already exists",
                               name=account,password=password,password_repeat=repeatPassword,
                               seed=seed)
    
    # Create the account
    response = account_module.importWallet(account,password,seed)

    if 'error' in response:
        return render_template("import-wallet.html",
                               error=response['error'],
                               name=account,password=password,password_repeat=repeatPassword,
                               seed=seed)
    
    add_alert("Rescan needed", "Please rescan the wallet after importing to see all transactions", account)
    # Set the cookie
    response = make_response(redirect("/"))
    response.set_cookie("account", account+":"+password)
    return response

@app.route('/report')
def report():
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    csv = '\n'.join(account_module.generateReport(account))
    # Create a download

    response = make_response(csv)
    response.headers["Content-Disposition"] = "attachment; filename=report.csv"
    response.headers["Content-Type"] = "text/csv"
    return response
    

#endregion

#region Plugins
@app.route('/plugins')
def plugins_index():
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")

    plugins = render.plugins(plugins_module.listPlugins(True))

    return render_template("plugins.html", account=account, 
                           
                           plugins=plugins)

@app.route('/plugin/<ptype>/<path:plugin>')
def plugin(ptype,plugin):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")

    plugin = f"{ptype}/{plugin}"

    if not plugins_module.pluginExists(plugin):
        logger.warning(f"Plugin not found: {plugin}")
        return redirect("/plugins")

    data = plugins_module.getPluginData(plugin)

    functions = plugins_module.getPluginFunctions(plugin)
    functions = render.plugin_functions(functions,plugin)

    if not data['verified']:
        functions = "<div class='container-fluid'><div class='alert alert-warning' role='alert'>This plugin is not verified and is disabled for your protection. Please check the code before marking the plugin as verified <a href='/plugin/" + plugin + "/verify' class='btn btn-danger'>Verify</a></div></div>" + functions

    
    error = request.args.get("error")
    if error is None:
        error = ""

    return render_template("plugin.html", account=account, 
                           
                           name=data['name'],description=data['description'],
                           author=data['author'],version=data['version'],
                           source=data['source'],functions=functions,error=error)

@app.route('/plugin/<ptype>/<path:plugin>/verify')
def plugin_verify(ptype,plugin):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")
    
    plugin = f"{ptype}/{plugin}"

    if not plugins_module.pluginExists(plugin):
        return redirect("/plugins")

    data = plugins_module.getPluginData(plugin)

    if not data['verified']:
        plugins_module.verifyPlugin(plugin)

    return redirect("/plugin/" + plugin)

@app.route('/plugin/<ptype>/<path:plugin>/<function>', methods=["POST"])
def plugin_function(ptype,plugin,function):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")

    plugin = f"{ptype}/{plugin}"

    if not plugins_module.pluginExists(plugin):
        return redirect("/plugins")

    data = plugins_module.getPluginData(plugin)

    # Get plugin/main.py listfunctions()
    if function in plugins_module.getPluginFunctions(plugin):
        inputs = plugins_module.getPluginFunctionInputs(plugin,function)
        request_data = {}
        for input in inputs:
            request_data[input] = request.form.get(input)
            
            if inputs[input]['type'] == "address":
                # Handle hip2
                address_check = account_module.check_address(request_data[input],True,True)
                if not address_check:
                    return redirect("/plugin/" + plugin + "?error=Invalid address")
                request_data[input] = address_check
            elif inputs[input]['type'] == "dns":
                # Handle URL encoding of DNS
                request_data[input] = urllib.parse.unquote(request_data[input])

        response = plugins_module.runPluginFunction(plugin,function,request_data,request.cookies.get("account"))
        if not response:
            return redirect("/plugin/" + plugin + "?error=An error occurred")
        if 'error' in response:
            return redirect("/plugin/" + plugin + "?error=" + response['error'])
        outputs = plugins_module.getPluginFunctionReturns(plugin,function)
        # Check outputs
        for output in outputs:
            if outputs[output]['type'] == "file":
                data = io.BytesIO(response[output].encode('utf-8'))
                return send_file(data, as_attachment=True, download_name=outputs[output]['name'])

        response = render.plugin_output(response,outputs)
        return render_template("plugin-output.html", account=account,name=data['name'],
                               description=data['description'],output=response)

    else:
        return jsonify({"error": "Function not found"})

#endregion

#region API Routes
@app.route('/api/v1/hsd/<function>', methods=["GET"])
def api_hsd(function):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return jsonify({"error": "Not logged in"})
    
    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return jsonify({"error": "Invalid account"})
    
    if function == "sync":
        return jsonify({"result": account_module.getNodeSync()})
    if function == "version":
        return jsonify({"result": account_module.hsdVersion(False)})
    if function == "height":
        return jsonify({"result": account_module.getBlockHeight()})
    if function == "mempool":
        return jsonify({"result": account_module.getMempoolTxs()})
    if function == "mempoolBids":
        return jsonify({"result": account_module.getMempoolBids()})
    if function == "nextAuctionState":
        # Get the domain from the query parameters
        domain = request.args.get('domain')
        if not domain:
            return jsonify({"error": "No domain specified"}), 400
        domainInfo = account_module.getDomain(domain)
        if 'error' in domainInfo and domainInfo['error'] is not None:
            return jsonify({"error": domainInfo['error']}), 400
        stats = domainInfo['info']['stats'] if 'stats' in domainInfo['info'] else {}
        state = domainInfo['info']['state']
        next_action = ""
        next = ""
        if state == 'CLOSED':
            if not domainInfo['info']['registered']:
                if account_module.isOwnDomain(account,domain):
                    state = 'PENDING REGISTER'
                    next = "Pending Register"
                    next_action = f'<a href="/auction/{domain}/register">Register Domain</a>'
                
                else:
                    state = 'AVAILABLE'
                    next = "Available Now"
                    next_action = f'<a href="/auction/{domain}/open">Open Auction</a>'
            else:
                state = 'REGISTERED'
                expires = domainInfo['info']['stats']['daysUntilExpire']
                next = f"Expires in ~{expires} days"
        elif state == "REVOKED":
            next = "Available Now"
            next_action = f'<a href="/auction/{domain}/open">Open Auction</a>'
        elif state == 'OPENING':
            next = f"Bidding opens in {str(stats['blocksUntilBidding'])} blocks (~{blocks_to_time(stats['blocksUntilBidding'])})"
        elif state == 'BIDDING':
            next = f"Reveal in {stats['blocksUntilReveal']} blocks (~{blocks_to_time(stats['blocksUntilReveal'])})"
            if stats['blocksUntilReveal'] == 1:
                next += "<br>Bidding no longer possible"
            elif stats['blocksUntilReveal'] == 2:
                next += "<br>LAST CHANCE TO BID"
            elif stats['blocksUntilReveal'] == 3:
                next += "<br>Next block is last chance to bid"
            elif stats['blocksUntilReveal'] < 6:
                next += f"<br>Last chance to bid in {stats['blocksUntilReveal']-2} blocks"


        elif state == 'REVEAL':
            next = f"Reveal ends in {str(stats['blocksUntilClose'])} blocks (~{blocks_to_time(stats['blocksUntilClose'])})"
            next_action = f'<a href="/auction/{domain}/reveal">Reveal All</a>'

        return jsonify({
            "state": state,
            "next": next,
            "next_action": next_action
        })


    return jsonify({"error": "Invalid function", "result": "Invalid function"}), 400


@app.route('/api/v1/hsd/<function>/mobile', methods=["GET"])
def api_hsd_mobile(function):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return jsonify({"error": "Not logged in"})
    
    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return jsonify({"error": "Invalid account"})
    
    if function == "sync":
        sync = account_module.getNodeSync()
        if sync == 100:
            # Don't show sync percentage on mobile
            sync = ""
        elif sync == -1:
            sync = "HSD Error"
        else:
            sync = f"{sync}%"
        return jsonify({"result": sync})
    
    return jsonify({"error": "Invalid function", "result": "Invalid mobile function"}), 400

@app.route('/api/v1/wallet/<function>', methods=["GET"])
def api_wallet(function):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return jsonify({"error": "Not logged in"})
    
    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return jsonify({"error": "Invalid account"})

    password = request.cookies.get("account","").split(":")[1]
    if not account:
        return jsonify({"error": "Invalid account"})
    
    if function == "sync":
        return jsonify({"result": account_module.getWalletStatus()})
    
    if function == "available":
        return jsonify({"result": account_module.getBalance(account)['available']})
    if function == "total":
        return jsonify({"result": account_module.getBalance(account)['total']})
    if function == "pending":
        return jsonify({"result": account_module.getPendingTX(account)})
    if function == "locked":
        return jsonify({"result": account_module.getBalance(account)['locked']})
    
    if function == "domainCount":
        return jsonify({"result": len(account_module.getDomains(account))})
    
    if function == "bidCount":
        return jsonify({"result": len(account_module.getBids(account))})
    
    if function == "pendingReveal":
        return jsonify({"result": account_module.getPendingReveals(account)})
    if function == "pendingRegister":
        return jsonify({"result": account_module.getPendingRegisters(account)})
    if function == "pendingRedeem":
        return jsonify({"result": account_module.getPendingRedeems(account,password)})
    
    if function == "pendingFinalize":
        return jsonify({"result": account_module.getPendingFinalizes(account,password)})

    if function == "domains":
        domains = account_module.getDomains(account)
        if type(domains) is dict and 'error' in domains:
            return jsonify({"result": [], "error": domains['error']})
        
        # Add nameRender to each domain
        for domain in domains:
            domain['nameRender'] = renderDomain(domain['name'])

        return jsonify({"result": domains})
    
    if function == "transactions":
        # Get the page parameter
        page = request.args.get('page', 1)
        try:
            page = int(page)
        except ValueError:
            page = 1

        if page < 1:
            page = 1
            
        # Check for force refresh parameter
        force_refresh = request.args.get('refresh') == 'true'
        
        # Create a cache key based on account and page
        cache_key = f"{account}_{page}"
        
        # Check if data is in cache and not expired
        current_time = time.time()
        if not force_refresh and cache_key in tx_cache and (current_time - tx_cache[cache_key]['time'] < TX_CACHE_TIMEOUT):
            transactions = tx_cache[cache_key]['data']
            txCount = len(transactions)
            transactions_html = render.transactions(transactions)
        else:
            # Fetch transactions from account module
            transactions = account_module.getTransactions(account, page)
            txCount = len(transactions)
            transactions_html = render.transactions(transactions)
            
            # Store in cache
            tx_cache[cache_key] = {
                'data': transactions,
                'html': transactions_html,
                'time': current_time
            }
        
        return jsonify({
            "html": transactions_html,
            "txCount": txCount,
            "page": page
        })

    if function == "domainBids":
        domain = request.args.get('domain')
        if not domain:
            return jsonify({"error": "No domain specified"}), 400
        bids = account_module.getBids(account,domain)
        if bids == []:
            return jsonify({"result": [], "error": "No bids found"}), 404
        else:
            reveals = account_module.getReveals(account,domain)
            for reveal in reveals:
                # Get TX
                revealInfo = account_module.getRevealTX(reveal)
                reveal['bid'] = revealInfo
            bids = render.bids(bids,reveals)
        return jsonify({"result": bids})

    if function == "icon":
        # Check if there is an icon
        if not os.path.exists('user_data/images'):
            return send_file('templates/assets/img/HNS.png')
        files = os.listdir('user_data/images')
        for file in files:
            if file.startswith(account):
                return send_file(f'user_data/images/{file}')
            
        return send_file('templates/assets/img/HNS.png')

    return jsonify({"error": "Invalid function", "result": "Invalid function"}), 400

@app.route('/api/v1/wallet/<function>/mobile', methods=["GET"])
def api_wallet_mobile(function):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return jsonify({"error": "Not logged in"})
    
    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return jsonify({"error": "Invalid account"})
    
    if function == "sync":
        sync = account_module.getWalletStatus()
        if sync == "Ready":
            # Don't show sync percentage on mobile
            sync = ""
        elif sync == "Error wallet ahead of node":
            sync = "HSW Sync Error"
        else:
            sync = "HSW Syncing"        
        return jsonify({"result": sync})

    return jsonify({"error": "Invalid function", "result": "Invalid mobile function"}), 400
    
@app.route('/api/v1/icon/<account>')
def api_icon(account):
    if not os.path.exists('user_data/images'):
        return send_file('templates/assets/img/HNS.png')
    files = os.listdir('user_data/images')
    for file in files:
        if file.startswith(account):
            return send_file(f'user_data/images/{file}')
    return send_file('templates/assets/img/HNS.png')


@app.route('/api/v1/status')
def api_status():
    # This doesn't require a login
    # Check if the node is connected
    node_status = {
        "connected": account_module.hsdConnected(),
        "internal": account_module.HSD_INTERNAL_NODE,
        "internal_running": False,
        "version": "N/A"
    }
    status = 200
    error = None
    node_status['version'] = account_module.hsdVersion(False) # type: ignore

    if node_status['internal']:
        node_status['internal_running'] = account_module.hsdRunning()
    
    # If the node is not connected, return an error
    if not node_status['connected']:
        error = "Node not connected"
        status = 503
    if node_status['version'] == -1:
        error = "Error connecting to HSD"
        status = 503
    if node_status['internal'] and not node_status['internal_running']:
        error = "Internal node not running"
        status = 503
    

    return jsonify({
        "node": node_status,
        "error": error,
        "status": status
    }), status


#endregion

#region Helper functions
def blocks_to_time(blocks: int) -> str:
    """
    Convert blocks to time in a human-readable format.
    Blocks are mined approximately every 10 minutes.
    """
    if blocks < 0:
        return "Invalid time"
    
    if blocks < 6:
        return f"{blocks * 10} mins"
    elif blocks < 144:
        hours = blocks // 6
        minutes = (blocks % 6) * 10
        if minutes == 0:
            return f"{hours} hrs"

        return f"{hours} hrs {minutes} mins"
    else:
        days = blocks // 144
        hours = (blocks % 144) // 6
        if hours == 0:
            return f"{days} days"
        return f"{days} days {hours} hrs"

def renderDomain(name: str) -> str:
    """
    Render a domain name with emojis and other special characters.
    """
    # Convert emoji to punycode
    try:
        rendered = name.encode("ascii").decode("idna") 
        if rendered == name:
            return f"{name}/"
        return f"{rendered}/ ({name})"


    except Exception:
        return f"{name}/"

def get_alerts(account:str) -> list:
    """
    Get alerts to show on the dashboard.
    """
    
    alerts = []

    info = gitinfo.get_git_info()
    if info is not None:    
        branch = info['refs']
        commit = info['commit']
        if commit != latestVersion(branch):
            logger.info("New version available")
            alerts.append({
                "name": "Update Available",
                "output": f"A new version of FireWallet is available. <a href='https://git.woodburn.au/nathanwoodburn/firewalletbrowser/compare/{commit}...{branch}' target='_blank'>Changelog</a>"
            })

    


    # Check if the node is connected
    if not account_module.hsdConnected():
        alerts.append({
            "name": "Node",
            "output": "HSD node is not connected. Please check your settings."
        })
        return alerts

    # Check if the wallet is synced
    wallet_status = account_module.getWalletStatus()
    if wallet_status != "Ready":
        alerts.append({
            "name": "Wallet",
            "output": f"The wallet is not synced ({wallet_status}). Please wait for it to sync."
        })
    # Try to read from notifications sqlite database
    if os.path.exists("user_data/notifications.db"):
        try:
            conn = sqlite3.connect("user_data/notifications.db")
            c = conn.cursor()
            c.execute("SELECT id, name, message FROM notifications WHERE read=0 AND (account=? OR account='all')", (account,))
            rows = c.fetchall()
            for row in rows:
                alerts.append({
                    "id": row[0],
                    "name": row[1],
                    "output": row[2]
                })
            conn.close()
        except Exception as e:
            logger.error(f"Error reading notifications: {e}")
            pass
        
    return alerts

def add_alert(name:str,output:str,account:str="all"):
    """
    Add an alert to the notifications database.
    
    name: Name of the alert
    output: Message of the alert
    account: Account to add the alert for (default: all)
    """
    if not os.path.exists("user_data/notifications.db"):
        conn = sqlite3.connect("user_data/notifications.db")
        c = conn.cursor()
        c.execute("CREATE TABLE notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, message TEXT, account TEXT, read INTEGER DEFAULT 0)")
        conn.commit()
        conn.close()
    
    try:
        conn = sqlite3.connect("user_data/notifications.db")
        c = conn.cursor()
        c.execute("INSERT INTO notifications (name, message, account) VALUES (?, ?, ?)", (name, output, account))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error adding notification: {e}")
        pass

def dismiss_alert(alert_id:int,account:str="all"):
    """
    Mark an alert as read.

    alert_id: ID of the alert to dismiss
    account: Account to dismiss the alert for (default: all)
    """
    if not os.path.exists("user_data/notifications.db"):
        return
    
    try:
        conn = sqlite3.connect("user_data/notifications.db")
        c = conn.cursor()
        c.execute("UPDATE notifications SET read=1 WHERE id=?", (alert_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error dismissing notification: {e}")
        pass

@app.route('/dismiss/<int:alert_id>')
@app.route('/api/v1/dismiss/<int:alert_id>')
def dismiss_alert_route(alert_id):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")
    
    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")

    dismiss_alert(alert_id,account)
    return redirect(request.referrer or "/")

#endregion


#region Assets and default pages
@app.route('/qr/<data>')
def qr(data):

    output = qrcode(data, mode="raw")
    if output is None:
        return jsonify({"error": "Invalid data"}), 400
    return send_file(output, mimetype="image/png")

# Theme
@app.route('/assets/css/styles.min.css')
def send_css():
    if THEME == "live":
        return send_from_directory('templates/assets/css', 'styles.min.css')
    return send_from_directory('themes', f'{THEME}.css')

@app.route('/assets/<path:path>')
def send_assets(path):
    return send_from_directory('templates/assets', path)

# Try path
@app.route('/<path:path>')
def try_path(path):
    # Check if node connected
    if not account_module.hsdConnected():
        return redirect("/login?message=Node not connected")

    if os.path.isfile("templates/" + path + ".html"):
        return render_template(path + ".html")
    else:
        return page_not_found(404)

@app.errorhandler(404)
def page_not_found(e):
    logger.warning(f"404 Not Found: {request.path}")
    account = account_module.check_account(request.cookies.get("account"))
    return render_template('404.html',account=account), 404
#endregion

if __name__ == '__main__':
    host = '127.0.0.1'
    port = 5000
    # Check if --host is in the command line arguments
    if "--host" in sys.argv:
        host_index = sys.argv.index("--host") + 1
        if host_index < len(sys.argv):
            host = sys.argv[host_index]
    # Check if --port is in the command line arguments
    if "--port" in sys.argv:
        port_index = sys.argv.index("--port") + 1
        if port_index < len(sys.argv):
            try:
                port = int(sys.argv[port_index])
            except ValueError:
                pass
    print(f"Starting FireWallet on http://{host}:{port}",flush=True)
    
    if "--debug" in sys.argv:
        console_handler = logging.StreamHandler(sys.stdout)
        # Use a simple format for console
        console_formatter = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.WARNING)
        logger.addHandler(console_handler)
        logger.setLevel(logging.DEBUG)
        app.run(debug=True, host=host, port=port)
    else:        
        app.run(host=host, port=port)

def tests():
    assert blocks_to_time(6) == "1 hrs"
    assert blocks_to_time(3) == "30 mins"
    assert blocks_to_time(1) == "10 mins"
    assert blocks_to_time(10) == "1 hrs 40 mins"