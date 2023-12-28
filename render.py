def domains(domains):
    html = ''
    for domain in domains:
        owner = domain['owner']
        if 'index' in owner:
            if owner['index'] == 0:
                continue
        expires = domain['stats']
        if 'daysUntilExpire' in expires:
            expires = expires['daysUntilExpire']
        paid = domain['value']
        paid = paid / 1000000



        html += f'<tr><td>{domain["name"]}</td><td>{expires} days</td><td>{paid} HNS</td><td><a href="/domain/{domain["name"]}">Manage</a></td></tr>'
    
    return html

def transactions(txs):
    html = ''

    # Reverse the list
    txs = txs[::-1]

    for tx in txs:
        action = "HNS Transfer"
        address = tx["outputs"][0]["address"]
        hash = tx["hash"]
        confirmations=tx["confirmations"]
        amount = 0
        incomming = False
        if not tx["inputs"][0]["path"]:
            incomming = True

        for output in tx["outputs"]:
            if output["covenant"]["action"] != "NONE":
                if action == "HNS Transfer":
                    action = output["covenant"]["action"]
                elif action == output["covenant"]["action"]:
                    continue
                else:
                    action = "Multiple Actions"

            if not output["path"] and not incomming:
                amount += output["value"]
            elif output["path"] and incomming:
                amount += output["value"]

        amount = amount / 1000000
        amount = round(amount, 2)
        amount = "{:,}".format(amount)

        hash = "<a target='_blank' href='https://niami.io/tx/" + hash + "'>" + hash[:8] + "...</a>"
        if confirmations < 5:
            confirmations = "<td style='background-color: red;'>" + str(confirmations) + "</td>"
        else:
            confirmations = "<td>" + str(confirmations) + "</td>"


        html += f'<tr><td>{action}</td><td>{address}</td><td>{hash}</td>{confirmations}<td>{amount} HNS</td></tr>'

            



    return html