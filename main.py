import json
import random
from flask import Flask, make_response, redirect, request, jsonify, render_template, send_from_directory,send_file
import os
import dotenv
import requests
import account as account_module
import render
import re
from flask_qrcode import QRcode
import domainLookup
import urllib.parse
import importlib
import plugin as plugins_module
import gitinfo
import datetime

dotenv.load_dotenv()

app = Flask(__name__)
qrcode = QRcode(app)


# Change this if network fees change
fees = 0.02
revokeCheck = random.randint(100000,999999)


theme = os.getenv("theme")

@app.route('/')
def index():
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")
    
    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")

    balance = account_module.getBalance(account)
    available = balance['available']
    total = balance['total']

    # Add commas to the numbers
    available = "{:,}".format(available)
    total = "{:,}".format(total)

    pending = account_module.getPendingTX(account)
    domains = account_module.getDomains(account)

    # Sort
    sort = request.args.get("sort")
    if sort == None:
        sort = "domain"
    sort = sort.lower()
    sort_price = ""
    sort_price_next = "⬇"
    sort_expiry = ""
    sort_expiry_next = "⬇"
    sort_domain = ""
    sort_domain_next = "⬇"
    reverse = False

    direction = request.args.get("direction")
    if direction == None:
        direction = "⬇"

    if direction == "⬆":
        reverse = True

    if sort == "expiry":
        # Sort by next expiry
        domains = sorted(domains, key=lambda k: k['renewal'],reverse=reverse)
        sort_expiry = direction
        sort_expiry_next = reverseDirection(direction)

    
    elif sort == "price":
        # Sort by price
        domains = sorted(domains, key=lambda k: k['value'],reverse=reverse)
        sort_price = direction
        sort_price_next = reverseDirection(direction)
    else:
        # Sort by domain
        domains = sorted(domains, key=lambda k: k['name'],reverse=reverse)
        sort_domain = direction
        sort_domain_next = reverseDirection(direction)
        
    
    

    
    domain_count = len(domains)
    domainsMobile = render.domains(domains,True)
    domains = render.domains(domains)
    
    plugins = ""
    dashFunctions = plugins_module.getDashboardFunctions()
    for function in dashFunctions:
        functionOutput = plugins_module.runPluginFunction(function["plugin"],function["function"],{},request.cookies.get("account"))
        plugins += render.plugin_output_dash(functionOutput,plugins_module.getPluginFunctionReturns(function["plugin"],function["function"]))

    return render_template("index.html", account=account, available=available,
                           total=total, pending=pending, domains=domains,
                           domainsMobile=domainsMobile, plugins=plugins,
                           domain_count=domain_count, sync=account_module.getNodeSync(),
                           sort_price=sort_price,sort_expiry=sort_expiry,
                           sort_domain=sort_domain,sort_price_next=sort_price_next,
                           sort_expiry_next=sort_expiry_next,sort_domain_next=sort_domain_next)
 
def reverseDirection(direction: str):
    if direction == "⬆":
        return "⬇"
    else:
        return "⬆"


#region Transactions
@app.route('/tx')
def transactions():
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))

    # Get the transactions
    transactions = account_module.getTransactions(account)
    transactions = render.transactions(transactions)

    return render_template("tx.html", account=account, sync=account_module.getNodeSync(),
                           tx=transactions)


@app.route('/send')
def send_page():
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
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
        

    return render_template("send.html", account=account,sync=account_module.getNodeSync(),
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
        return redirect("/send?message=Invalid address or amount&address=" + address + "&amount=" + amount)
    
    address_check = account_module.check_address(address,True,True)
    if not address_check:
        return redirect("/send?message=Invalid address&address=" + address + "&amount=" + amount)
    
    address = address_check
    # Check if the amount is valid
    if re.match(r"^\d+(\.\d+)?$", amount) is None:
        return redirect("/send?message=Invalid amount&address=" + address + "&amount=" + amount)
    
    # Check if the amount is valid
    amount = float(amount)
    if amount <= 0:
        return redirect("/send?message=Invalid amount&address=" + address + "&amount=" + str(amount))
    
    if amount > account_module.getBalance(account)['available'] - fees:
        return redirect("/send?message=Not enough funds to transfer&address=" + address + "&amount=" + str(amount))
    
    toAddress = address
    if request.form.get('address') != address:
        toAddress = request.form.get('address') + "<br>" + address

    action = f"Send HNS to {request.form.get('address')}"
    content = f"Are you sure you want to send {amount} HNS to {toAddress}<br><br>"
    content += f"This will cost {amount} HNS + mining fees and is not able to be undone."

    cancel = f"/send"
    confirm = f"/send/confirm?address={address}&amount={amount}"


    return render_template("confirm.html", account=account_module.check_account(request.cookies.get("account")),
                            sync=account_module.getNodeSync(),action=action,
                            content=content,cancel=cancel,confirm=confirm)
    

@app.route('/send/confirm')
def sendConfirmed():

    address = request.args.get("address")
    amount = float(request.args.get("amount"))
    response = account_module.send(request.cookies.get("account"),address,amount)
    if 'error' in response:
        return redirect("/send?message=" + response['error'] + "&address=" + address + "&amount=" + str(amount))
    
    return redirect("/success?tx=" + response['tx'])
    


@app.route('/receive')
def receive():
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")
    
    address = account_module.getAddress(account)

    return render_template("receive.html", account=account,sync=account_module.getNodeSync(),
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
    return render_template("success.html", account=account,sync=account_module.getNodeSync(),
                            tx=tx)

@app.route('/checkaddress')
def check_address():
    address = request.args.get("address")
    if address is None:
        return jsonify({"result": "Invalid address"})
    
    return jsonify({"result": account_module.check_address(address)})
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

    balance = account_module.getBalance(account)
    locked = balance['locked']

    # Add commas to the numbers
    locked = "{:,}".format(locked)


    bids = account_module.getBids(account)
    domains = account_module.getDomains(account,False)
    
    # Sort
    sort = request.args.get("sort")
    if sort == None:
        sort = "domain"
    sort = sort.lower()
    sort_price = ""
    sort_price_next = "⬇"
    sort_state = ""
    sort_state_next = "⬇"
    sort_domain = ""
    sort_domain_next = "⬇"
    reverse = False

    direction = request.args.get("direction")
    if direction == None:
        direction = "⬇"

    if direction == "⬆":
        reverse = True

    if sort == "price":
        # Sort by price
        bids = sorted(bids, key=lambda k: k['value'],reverse=reverse)
        sort_price = direction
        sort_price_next = reverseDirection(direction)
    elif sort == "state":
        sort_state = direction
        sort_state_next = reverseDirection(direction)
        domains = sorted(domains, key=lambda k: k['state'],reverse=reverse)
    else:
        # Sort by domain
        bids = sorted(bids, key=lambda k: k['name'],reverse=reverse)
        sort_domain = direction
        sort_domain_next = reverseDirection(direction)
    
    if sort == "state":
        bidsHtml = render.bidDomains(bids,domains,True)
    else:
        bidsHtml = render.bidDomains(bids,domains)
    

    pending_reveals = 0
    for domain in domains:
        if domain['state'] == "REVEAL":
            for bid in bids:
                if bid['name'] == domain['name']:
                    bid_found = False
                    reveals = account_module.getReveals(account,domain['name'])
                    for reveal in reveals:
                        if reveal['own'] == True:
                            if bid['value'] == reveal['value']:
                                bid_found = True
                    if not bid_found:
                        pending_reveals += 1

    plugins = ""
    # dashFunctions = plugins_module.getDashboardFunctions()
    # for function in dashFunctions:
    #     functionOutput = plugins_module.runPluginFunction(function["plugin"],function["function"],{},request.cookies.get("account"))
        # plugins += render.plugin_output_dash(functionOutput,plugins_module.getPluginFunctionReturns(function["plugin"],function["function"]))

    message = ''
    if 'message' in request.args:
        message = request.args.get("message")
    return render_template("auctions.html", account=account, locked=locked, domains=bidsHtml,
                           domainsMobile=bidsHtml, plugins=plugins,
                           domain_count=bidsHtml, sync=account_module.getNodeSync(),
                           sort_price=sort_price,sort_state=sort_state,
                           sort_domain=sort_domain,sort_price_next=sort_price_next,
                           sort_state_next=sort_state_next,sort_domain_next=sort_domain_next,
                           bids=len(bids),reveal=pending_reveals,message=message)

@app.route('/reveal')
def revealAllBids():
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")
    
    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")

    response = account_module.revealAll(request.cookies.get("account"))
    if 'error' in response:
        print(response)
        if response['error'] != None:
            if response['error']['message'] == "Nothing to do.":
                return redirect("/auctions?message=No reveals pending")
            return redirect("/auctions?message=" + response['error']['message'])
            
    return redirect("/success?tx=" + response['hash'])


@app.route('/search')
def search():
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")
    
    search_term = request.args.get("q")
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
        functionOutput = plugins_module.runPluginFunction(function["plugin"],function["function"],{"domain":search_term},account_module.check_account(request.cookies.get("account")))
        plugins += render.plugin_output(functionOutput,plugins_module.getPluginFunctionReturns(function["plugin"],function["function"]))

    plugins += "</div>"

    if 'error' in domain:
        return render_template("search.html", account=account,sync=account_module.getNodeSync(),
                               search_term=search_term, domain=domain['error'],plugins=plugins)
    
    if domain['info'] is None:
        return render_template("search.html", account=account, sync=account_module.getNodeSync(),
                               search_term=search_term,domain=search_term,
                               state="AVAILABLE", next="Available Now",plugins=plugins)

    state = domain['info']['state']
    if state == 'CLOSED':
        if domain['info']['registered']:
            state = 'REGISTERED'
            expires = domain['info']['stats']['daysUntilExpire']
            next = f"Expires in ~{expires} days"
        else:
            state = 'AVAILABLE'
            next = "Available Now"
    elif state == "REVOKED":
            next = "Available Now"
    elif state == 'OPENING':
        next = "Bidding opens in ~" + str(domain['info']['stats']['blocksUntilBidding']) + " blocks"
    elif state == 'BIDDING':
        next = "Reveal in ~" + str(domain['info']['stats']['blocksUntilReveal']) + " blocks"
    elif state == 'REVEAL':
        next = "Reveal ends in ~" + str(domain['info']['stats']['blocksUntilClose']) + " blocks"



    domain_info = domainLookup.niami_info(search_term)
    owner = 'Unknown'
    dns = []
    txs = []

    if domain_info:
        owner = domain_info['owner']
        dns = domain_info['dns']
        txs = domain_info['txs']

    own_domains = account_module.getDomains(account)
    own_domains = [x['name'] for x in own_domains]
    own_domains = [x.lower() for x in own_domains]
    if search_term in own_domains:
        owner = "You"

    dns = render.dns(dns)
    txs = render.txs(txs)

    return render_template("search.html", account=account, sync=account_module.getNodeSync(),
                           search_term=search_term,domain=domain['info']['name'],
                           raw=domain,state=state, next=next, owner=owner,
                           dns=dns, txs=txs,plugins=plugins)
    
@app.route('/manage/<domain>')
def manage(domain: str):
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
    
    domain_info = account_module.getDomain(domain)
    if 'error' in domain_info:
        return render_template("manage.html", account=account, sync=account_module.getNodeSync(),
                               domain=domain, error=domain_info['error'])
    
    expiry = domain_info['info']['stats']['daysUntilExpire']
    dns = account_module.getDNS(domain)
    raw_dns = str(dns).replace("'",'"')
    dns = render.dns(dns)

    errorMessage = request.args.get("error")
    if errorMessage == None:
        errorMessage = ""
    address = request.args.get("address")
    if address == None:
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
        functionOutput = plugins_module.runPluginFunction(function["plugin"],function["function"],{"domain":domain},account_module.check_account(request.cookies.get("account")))
        plugins += render.plugin_output(functionOutput,plugins_module.getPluginFunctionReturns(function["plugin"],function["function"]))

    plugins += "</div>"


    return render_template("manage.html", account=account, sync=account_module.getNodeSync(),
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
    print(domain)
    response = account_module.finalize(request.cookies.get("account"),domain)
    if response['error'] != None:
        print(response)
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
    print(domain)
    response = account_module.cancelTransfer(request.cookies.get("account"),domain)
    if 'error' in response:
        if response['error'] != None:
            print(response)
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
    content += f"This will return the domain to the auction pool and you will lose any funds spent on the domain.<br>"
    content += f"This cannot be undone after the transaction is sent.<br><br>"
    content += f"Please enter your password to confirm."

    cancel = f"/manage/{domain}"
    confirm = f"/manage/{domain}/revoke/confirm"
    action = f"Revoke {domain}/"   

    
    return render_template("confirm-password.html", account=account_module.check_account(request.cookies.get("account")),
                            sync=account_module.getNodeSync(),action=action,
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
    if response == False:
        return redirect("/manage/" + domain + "?error=Invalid password")


    response = account_module.revoke(request.cookies.get("account"),domain)
    if 'error' in response:
        if response['error'] != None:
            print(response)
            return redirect("/manage/" + domain + "?error=" + response['error']['message'])

    return redirect("/success?tx=" + response['hash'])

@app.route('/manage/<domain>/renew')
def renew(domain: str):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    
    if not account_module.check_account(request.cookies.get("account")):
        return redirect("/logout")
    
    domain = domain.lower()
    response = account_module.renewDomain(request.cookies.get("account"),domain)
    return redirect("/success?tx=" + response['hash'])

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
    if user_edits != None:
        dns = urllib.parse.unquote(user_edits)
    else:
        dns = account_module.getDNS(domain)
    
    dns = json.loads(dns)

    # Check if new records have been added
    dnsType = request.args.get("type")
    dnsValue = request.args.get("value")
    if dnsType != None and dnsValue != None:
        if dnsType != "DS":
            dns.append({"type": dnsType, "value": dnsValue})
        else:
            # Verify the DS record
            ds = dnsValue.split(" ")
            if len(ds) != 4:
                raw_dns = str(dns).replace("'",'"')
                return redirect("/manage/" + domain + "/edit?dns=" + urllib.parse.quote(str(raw_dns)) + "&error=Invalid DS record")
            
            try:
                ds[0] = int(ds[0])
                ds[1] = int(ds[1])
                ds[2] = int(ds[2])
            except:
                raw_dns = str(dns).replace("'",'"')
                return redirect("/manage/" + domain + "/edit?dns=" + urllib.parse.quote(str(raw_dns)) + "&error=Invalid DS record")
            finally:
                dns.append({"type": dnsType, "keyTag": ds[0], "algorithm": ds[1], "digestType": ds[2], "digest": ds[3]})

        dns = json.dumps(dns).replace("'",'"')
        return redirect("/manage/" + domain + "/edit?dns=" + urllib.parse.quote(dns))

    raw_dns = str(dns).replace("'",'"')
    dns = render.dns(dns,True)
    errorMessage = request.args.get("error")
    if errorMessage == None:
        errorMessage = ""

    
    return render_template("edit.html", account=account, sync=account_module.getNodeSync(),
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
    raw_dns = dns
    dns = urllib.parse.unquote(dns)
    response = account_module.setDNS(request.cookies.get("account"),domain,dns)
    if 'error' in response:
        print(response)
        return redirect("/manage/" + domain + "/edit?dns="+raw_dns+"&error=" + str(response['error']))
    return redirect("/success?tx=" + response['hash'])

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
        return redirect("/send?message=Invalid address&address=" + address)
    
    address = address_check
        
    toAddress = address
    if request.form.get('address') != address:
        toAddress = request.args.get('address') + "<br>" + address

    action = f"Send {domain}/ to {request.form.get('address')}"
    content = f"Are you sure you want to send {domain}/ to {toAddress}<br><br>"
    content += f"This requires sending a finalize transaction 2 days after the transfer is initiated."

    cancel = f"/manage/{domain}?address={address}"
    confirm = f"/manage/{domain}/transfer/confirm?address={address}"


    return render_template("confirm.html", account=account_module.check_account(request.cookies.get("account")),
                            sync=account_module.getNodeSync(),action=action,
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
    if signedMessage["error"] != None:
        return redirect("/manage/" + domain + "?error=" + signedMessage["error"])
    content += "Signature:<br><code>" + signedMessage["result"] + "</code><br><br>"

    data = {
        "domain": domain,
        "message": message,
        "signature": signedMessage["result"]
    }

    content += "Full information:<br><code style='text-align:left;display: block;'>" + json.dumps(data,indent=4).replace('\n',"<br>") + "</code><br><br>"

    content += "<textarea style='display: none;' id='data' rows='4' cols='50'>"+json.dumps(data)+"</textarea>"

    copyScript = "<script>function copyToClipboard() {var copyText = document.getElementById('data');copyText.style.display = 'block';copyText.select();copyText.setSelectionRange(0, 99999);document.execCommand('copy');copyText.style.display = 'none';var copyButton = document.getElementById('copyButton');copyButton.innerHTML='Copied';}</script>"
    content += "<button id='copyButton' onclick='copyToClipboard()' class='btn btn-secondary'>Copy to clipboard</button>" + copyScript

    

    return render_template("message.html", account=account,sync=account_module.getNodeSync(),
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
    
    return redirect("/success?tx=" + response['hash'])


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
    
    if 'error' in domainInfo:
        return render_template("auction.html", account=account,sync=account_module.getNodeSync(),
                               search_term=search_term, domain=domainInfo['error'])
    
    if domainInfo['info'] is None:
        next_action = f'<a href="/auction/{domain}/open">Open Auction</a>'
        return render_template("auction.html", account=account, sync=account_module.getNodeSync(),
                                search_term=search_term,domain=search_term,next_action=next_action,
                               state="AVAILABLE", next="Open Auction")

    state = domainInfo['info']['state']
    next_action = ''

    bids = account_module.getBids(account,search_term)
    if bids == []:
        bids = "No bids found"
        next_action = f'<a href="/auction/{domain}/scan">Rescan Auction</a>'
    else:
        reveals = account_module.getReveals(account,search_term)
        for reveal in reveals:
            # Get TX
            revealInfo = account_module.getRevealTX(reveal)
            reveal['bid'] = revealInfo
            print(revealInfo)
        bids = render.bids(bids,reveals)


    if state == 'CLOSED':
        if not domainInfo['info']['registered']:
            state = 'AVAILABLE'
            next = "Available Now"
            next_action = f'<a href="/auction/{domain}/open">Open Auction</a>'
        else:
            state = 'REGISTERED'
            expires = domainInfo['info']['stats']['daysUntilExpire']
            next = f"Expires in ~{expires} days"

            own_domains = account_module.getDomains(account)
            own_domains = [x['name'] for x in own_domains]
            own_domains = [x.lower() for x in own_domains]
            if search_term in own_domains:
                next_action = f'<a href="/manage/{domain}">Manage</a>'
    elif state == "REVOKED":
        next = "Available Now"
        next_action = f'<a href="/auction/{domain}/open">Open Auction</a>'
    elif state == 'OPENING':
        next = "Bidding opens in ~" + str(domainInfo['info']['stats']['blocksUntilBidding']) + " blocks"
    elif state == 'BIDDING':
        next = "Reveal in ~" + str(domainInfo['info']['stats']['blocksUntilReveal']) + " blocks"
    elif state == 'REVEAL':
        next = "Reveal ends in ~" + str(domainInfo['info']['stats']['blocksUntilClose']) + " blocks"
        next_action = f'<a href="/auction/{domain}/reveal">Reveal All</a>'

    message = ''
    if 'message' in request.args:
        message = request.args.get("message")


    return render_template("auction.html", account=account, sync=account_module.getNodeSync(),
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
    
    response = account_module.rescan_auction(account,domain)
    print(response)    
    return redirect("/auction/" + domain)

@app.route('/auction/<domain>/bid')
def bid(domain):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    
    if not account_module.check_account(request.cookies.get("account")):
        return redirect("/logout")
    
    domain = domain.lower()
    bid = request.args.get("bid")
    blind = request.args.get("blind")

    if bid == "":
        bid = 0
    if blind == "":
        blind = 0

    bid = float(bid)
    blind = float(blind)

    if bid+blind == 0:
        return redirect("/auction/" + domain+ "?message=Invalid bid amount")

    
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
                            sync=account_module.getNodeSync(),action=action,
                            domain=domain,content=content,cancel=cancel,confirm=confirm)

@app.route('/auction/<domain>/bid/confirm')
def bid_confirm(domain):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    
    if not account_module.check_account(request.cookies.get("account")):
        return redirect("/logout")
    
    domain = domain.lower()
    bid = request.args.get("bid")
    blind = request.args.get("blind")

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
    print(response)
    if 'error' in response:
        return redirect("/auction/" + domain + "?message=" + response['error']['message'])
    
    return redirect("/success?tx=" + response['hash'])

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
        if response['error'] != None:
            return redirect("/auction/" + domain + "?message=" + response['error']['message'])
    print(response)
    return redirect("/success?tx=" + response['hash'])

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
        return redirect("/auction/" + domain + "?message=" + response['error']['message'])
    return redirect("/success?tx=" + response['hash'])

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
    if error == None:
        error = ""
    success = request.args.get("success")
    if success == None:
        success = ""

    info = gitinfo.get_git_info()
    branch = info['refs']
    if branch != "main":
        branch = f"({branch})"
    else:
        branch = ""
    last_commit = info['author_date']
    # import to time from format "2024-02-13 11:24:03"
    last_commit = datetime.datetime.strptime(last_commit, "%Y-%m-%d %H:%M:%S")
    version = f'{last_commit.strftime("%y-%m-%d")} {branch}'

    return render_template("settings.html", account=account,sync=account_module.getNodeSync(),
                           error=error,success=success,version=version)

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
        return redirect("/settings?success=Resent transactions")
    elif action == "resend":
        resp = account_module.resendTXs()
        if 'error' in resp:
            return redirect("/settings?error=" + str(resp['error']))
        return redirect("/settings?success=Resent transactions")


    elif action == "zap":
        resp = account_module.zapTXs(request.cookies.get("account"))
        if 'error' in resp:
            return redirect("/settings?error=" + str(resp['error']))
        return redirect("/settings?success=Zapped transactions")
    elif action == "xpub":
        xpub = account_module.getxPub(request.cookies.get("account"))
        content = "<br><br>"
        content += "<textarea style='display: none;' id='data' rows='4' cols='50'>"+xpub+"</textarea>"
        content += "<script>function copyToClipboard() {var copyText = document.getElementById('data');copyText.style.display = 'block';copyText.select();copyText.setSelectionRange(0, 99999);document.execCommand('copy');copyText.style.display = 'none';var copyButton = document.getElementById('copyButton');copyButton.innerHTML='Copied';}</script>"
        content += "<button id='copyButton' onclick='copyToClipboard()' class='btn btn-secondary'>Copy to clipboard</button>"

        return render_template("message.html", account=account,sync=account_module.getNodeSync(),
                               title="xPub Key",
                               content="<code>"+xpub+"</code>" + content)

    return redirect("/settings?error=Invalid action")


#endregion


#region Account
@app.route('/login')
def login():
    wallets = account_module.listWallets()
    wallets = render.wallets(wallets)


    if 'message' in request.args:
        return render_template("login.html", sync=account_module.getNodeSync(),
                               error=request.args.get("message"),wallets=wallets)

    return render_template("login.html", sync=account_module.getNodeSync(),
                           wallets=wallets)

@app.route('/login', methods=["POST"])
def login_post():
    # Get the account and password
    account = request.form.get("account")
    password = request.form.get("password")

    # Check if the account is valid
    if account.count(":") > 0:
        return render_template("login.html", sync=account_module.getNodeSync(),
                               error="Invalid account")

    account = account + ":" + password

    # Check if the account is valid
    if not account_module.check_account(account):
        return render_template("login.html", sync=account_module.getNodeSync(),
                               error="Invalid account")


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
    response = make_response(render_template("message.html", sync=account_module.getNodeSync(),
                                              title="Account Created",
                                              content="Your account has been created. Here is your seed phrase. Please write it down and keep it safe as it will not be shown again<br><br>" + response['seed']))
    response.set_cookie("account", account+":"+password)
    return response

@app.route('/import-wallet', methods=["POST"])
def import_wallet():
    # Get the account and password
    account = request.form.get("name")
    password = request.form.get("password")
    repeatPassword = request.form.get("password_repeat")
    seed = request.form.get("seed")

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

    plugins = render.plugins(plugins_module.listPlugins())

    return render_template("plugins.html", account=account, sync=account_module.getNodeSync(),
                           plugins=plugins)

@app.route('/plugin/<plugin>')
def plugin(plugin):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")

    if not plugins_module.pluginExists(plugin):
        return redirect("/plugins")

    data = plugins_module.getPluginData(plugin)

    functions = plugins_module.getPluginFunctions(plugin)
    functions = render.plugin_functions(functions,plugin)

    if data['verified'] == False:
        functions = "<div class='container-fluid'><div class='alert alert-warning' role='alert'>This plugin is not verified and is disabled for your protection. Please check the code before marking the plugin as verified <a href='/plugin/" + plugin + "/verify' class='btn btn-danger'>Verify</a></div></div>" + functions

    
    error = request.args.get("error")
    if error == None:
        error = ""

    return render_template("plugin.html", account=account, sync=account_module.getNodeSync(),
                           name=data['name'],description=data['description'],
                           author=data['author'],version=data['version'],
                           functions=functions,error=error)

@app.route('/plugin/<plugin>/verify')
def plugin_verify(plugin):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")

    if not plugins_module.pluginExists(plugin):
        return redirect("/plugins")

    data = plugins_module.getPluginData(plugin)

    if data['verified'] == False:
        plugins_module.verifyPlugin(plugin)

    return redirect("/plugin/" + plugin)

@app.route('/plugin/<plugin>/<function>', methods=["POST"])
def plugin_function(plugin,function):
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")

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
        
        response = render.plugin_output(response,plugins_module.getPluginFunctionReturns(plugin,function))

        return render_template("plugin-output.html", account=account, sync=account_module.getNodeSync(),
                                    name=data['name'],description=data['description'],output=response)


    else:
        return jsonify({"error": "Function not found"})

#endregion


#region Assets and default pages
@app.route('/qr/<data>')
def qr(data):
    return send_file(qrcode(data, mode="raw"), mimetype="image/png")

# Theme
@app.route('/assets/css/styles.min.css')
def send_css():
    if theme == "live":
        return send_from_directory('templates/assets/css', 'styles.min.css')
    return send_from_directory('themes', f'{theme}.css')

@app.route('/assets/<path:path>')
def send_assets(path):
    return send_from_directory('templates/assets', path)

# Try path
@app.route('/<path:path>')
def try_path(path):
    if os.path.isfile("templates/" + path + ".html"):
        return render_template(path + ".html")
    else:
        return page_not_found(404)

@app.errorhandler(404)
def page_not_found(e):
    account = account_module.check_account(request.cookies.get("account"))

    return render_template('404.html',account=account), 404
#endregion

if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0')