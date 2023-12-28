from flask import Flask, make_response, redirect, request, jsonify, render_template, send_from_directory
import os
import dotenv
import requests
import account as account_module
import render

dotenv.load_dotenv()

app = Flask(__name__)


@app.route('/')
def index():
    # Check if the user is logged in
    if request.cookies.get("account") is None:
        return redirect("/login")
    
    account = account_module.check_account(request.cookies.get("account"))
    balance = account_module.getBalance(account)
    available = balance['available']
    total = balance['total']

    # Add commas to the numbers
    available = "{:,}".format(available)
    total = "{:,}".format(total)

    pending = account_module.getPendingTX(account)
    domains = account_module.getDomains(account)
    domains = render.domains(domains)


    return render_template("index.html", account=account, available=available,
                           total=total, pending=pending, domains=domains)
    

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












#region Account
@app.route('/login')
def login():
    if 'message' in request.args:
        return render_template("login.html", error=request.args.get("message"))

    accounts = account_module.getAccounts()

    return render_template("login.html", accounts=accounts)

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

@app.route('/assets/<path:path>')
def send_assets(path):
    return send_from_directory('templates/assets', path)

@app.errorhandler(404)
def page_not_found(e):
    account = account_module.check_account(request.cookies.get("account"))

    return render_template('404.html',account=account), 404

if __name__ == '__main__':
    app.run(debug=True)