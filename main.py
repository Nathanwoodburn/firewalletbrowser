from flask import Flask, make_response, redirect, request, jsonify, render_template, send_from_directory,send_file
import os
import dotenv
import requests
import account as account_module
import render
import re
from flask_qrcode import QRcode
import domainLookup

dotenv.load_dotenv()

app = Flask(__name__)
qrcode = QRcode(app)


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
    domain_count = len(domains)
    domains = render.domains(domains)
    


    return render_template("index.html", account=account, available=available,
                           total=total, pending=pending, domains=domains, domain_count=domain_count)
 
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

    return render_template("tx.html", account=account, tx=transactions)


@app.route('/send')
def send_page():
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    max = account_module.getBalance(account)['available']
    # Subtract approx fee of 0.02
    max = max - 0.02
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
        

    return render_template("send.html", account=account,max=max,message=message,
                           address=address,amount=amount)

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
    
    if amount > account_module.getBalance(account)['available'] - 0.02:
        return redirect("/send?message=Not enough funds to transfer&address=" + address + "&amount=" + str(amount))
    
    # Send the transaction
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

    return render_template("receive.html", account=account, address=address)
    
@app.route('/success')
def success():
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")

    account = account_module.check_account(request.cookies.get("account"))
    if not account:
        return redirect("/logout")

    tx = request.args.get("tx")
    return render_template("success.html", account=account, tx=tx)

@app.route('/checkaddress')
def check_address():
    address = request.args.get("address")
    if address is None:
        return jsonify({"result": "Invalid address"})
    
    return jsonify({"result": account_module.check_address(address)})
#endregion

#region Domains
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
    

    if len(search_term) == 0:
        return redirect("/")
    domain = account_module.getDomain(search_term)
    
    if 'error' in domain:
        return render_template("search.html", account=account, search_term=search_term, domain=domain['error'])
    
    print(domain)
    if domain['info'] is None:
        return render_template("search.html", account=account, search_term=search_term,
                               domain=search_term, state="AVAILABLE", next="Available Now")


    state = domain['info']['state']
    if state == 'CLOSED':
        if not domain['info']['registered']:
            state = 'AVAILABLE'
            next = "Available Now"
        else:
            state = 'REGISTERED'
            expires = domain['info']['stats']['daysUntilExpire']
            next = f"Expires in ~{expires} days"


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

        


    return render_template("search.html", account=account, search_term=search_term,
                           domain=domain['info']['name'],raw=domain,
                           state=state, next=next, owner=owner, dns=dns, txs=txs)
    


    


#endregion


#region Account
@app.route('/login')
def login():
    if 'message' in request.args:
        return render_template("login.html", error=request.args.get("message"))


    return render_template("login.html")

@app.route('/login', methods=["POST"])
def login_post():
    # Get the account and password
    account = request.form.get("account")
    password = request.form.get("password")

    # Check if the account is valid
    if account.count(":") > 0:
        return render_template("login.html", error="Invalid account")

    account = account + ":" + password

    # Check if the account is valid
    if not account_module.check_account(account):
        return render_template("login.html", error="Invalid account")


    # Set the cookie
    response = make_response(redirect("/"))
    response.set_cookie("account", account)
    return response

@app.route('/logout')
def logout():
    response = make_response(redirect("/login"))
    response.set_cookie("account", "", expires=0)
    return response

#endregion

#region Assets and default pages
@app.route('/qr/<data>')
def qr(data):
    return send_file(qrcode(data, mode="raw"), mimetype="image/png")

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
    app.run(debug=True)