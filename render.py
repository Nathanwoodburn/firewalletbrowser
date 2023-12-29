import datetime
import json


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



        html += f'<tr><td>{domain["name"]}</td><td>{expires} days</td><td>{paid} HNS</td><td><a href="/manage/{domain["name"]}">Manage</a></td></tr>'
    
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


def dns(data):
    html_output = ""
    
    for entry in data:
        html_output += f"<tr><td>{entry['type']}</td>\n"
        
        if entry['type'] != 'DS' and not entry['type'].startswith("GLUE") and not entry['type'].startswith("SYNTH"):
            for key, value in entry.items():
                if key != 'type':
                    if isinstance(value, list):
                        html_output += "<td>\n"
                        for val in value:
                            html_output += f"{val}<br>\n"

                        html_output += "</td>\n"
                    else:
                        html_output += f"<td>{value}</td>\n"


        elif entry['type'] == 'DS':
            ds = str(entry['keyTag']) + " " + str(entry['algorithm']) + " " + str(entry['digestType']) + " " + entry['digest']
            html_output += f"<td>{ds}</td>\n"

        else:
            value = ""
            for key, val in entry.items():
                if key != 'type':
                    value += str(val) + " "
            html_output += f"<td>{value}</td>\n"
            
        html_output += "  </tr>\n"    
    return html_output

def txs(data):
    data = data[::-1]

    html_output = ""

    for entry in data:
        html_output += f"<tr><td>{entry['action']}</td>\n"
        html_output += f"<td><a target='_blank' href='https://niami.io/tx/{entry['txid']}'>{entry['txid'][:8]}...</a></td>\n"
        amount = entry['amount']
        amount = amount / 1000000
        amount = round(amount, 2)

        if entry['blind'] == None:
            html_output += f"<td>{amount} HNS</td>\n"
        else:
            blind = entry['blind']
            blind = blind / 1000000
            blind = round(blind, 2)
            html_output += f"<td>{amount} + {blind} HNS</td>\n"

        html_output += f"<td>{timestamp_to_readable_time(entry['time'])}</td>\n"
        html_output += f"</tr>\n"

    return html_output


def timestamp_to_readable_time(timestamp):
    # Assuming the timestamp is in seconds
    dt_object = datetime.datetime.fromtimestamp(timestamp)
    readable_time = dt_object.strftime("%H:%M:%S %d %b %Y")
    return readable_time

def bids(bids,reveals):
    html = ''
    for bid in bids:
        lockup = bid['lockup']
        lockup = lockup / 1000000
        lockup = round(lockup, 2)
        html += "<tr>"
        html += f"<td>{lockup} HNS</td>"
        revealed = False
        for reveal in reveals:
            if reveal['bid'] == bid['prevout']['hash']:
                revealed = True
                value = reveal['value']
                value = value / 1000000
                value = round(value, 2)
                html += f"<td>{value} HNS</td>"
                bidValue = lockup - value
                bidValue = round(bidValue, 2)
                html += f"<td>{bidValue} HNS</td>"                               
                break
        if not revealed:
            html += f"<td>Hidden until reveal</td>"
            html += f"<td>Hidden until reveal</td>"
        if bid['own']:
            html += "<td>You</td>"
        else:
            html += "<td>Unknown</td>"
        html += "</tr>"

    return html