import datetime
import json
import urllib.parse
from flask import render_template
from domainLookup import punycode_to_emoji
import os

# Get Explorer URL
TX_EXPLORER_URL = os.getenv("EXPLORER_TX")
if TX_EXPLORER_URL is None:
    TX_EXPLORER_URL = "https://shakeshift.com/transaction/"



def domains(domains, mobile=False):
    html = ''
    for domain in domains:
        expires = domain['stats']
        if 'daysUntilExpire' in expires:
            expires = expires['daysUntilExpire']
        else:
            expires = "No expiration date"
        paid = domain['value']
        paid = paid / 1000000
        
        # Handle punycodes
        name = domain['name']
        emoji = punycode_to_emoji(name)
        if emoji != name:
            name = f'{emoji} ({name})'


        link = f'/manage/{domain["name"]}'
        link_action = "Manage"
        if domain['registered'] == False:
            link_action = "Register"
            link = f'/auction/{domain["name"]}/register'

        if not mobile:
            html += f'<tr><td>{name}</td><td>{expires} days</td><td>{paid:,.2f} HNS</td><td><a href="{link}">{link_action}</a></td></tr>'
        else:
            html += f'<tr><td><a href="{link}">{name}</a></td><td>{expires} days</td></tr>'
    
    return html

def transactions(txs):
    
    if len(txs) == 0:
        return '<tr><td colspan="5">No transactions found</td></tr>'
    html = ''
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

        hash = f"<a target='_blank' href='{TX_EXPLORER_URL}{hash}'>{hash[:8]}...</a>"
        if confirmations < 5:
            confirmations = f"<td style='background-color: red;'>{confirmations}</td>" 
        else:
            confirmations = f"<td>{confirmations:,}</td>"


        html += f'<tr><td>{action}</td><td>{address}</td><td>{hash}</td>{confirmations}<td>{amount:,.2f} HNS</td></tr>'
    return html


def dns(data, edit=False):
    html_output = ""
    index = 0
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
            ds = f"{entry['keyTag']} {entry['algorithm']} {entry['digestType']} {entry['digest']}"
            html_output += f"<td>{ds}</td>\n"

        else:
            value = ""
            for key, val in entry.items():
                if key != 'type':
                    value += f'{val} '
            html_output += f"<td>{value}</td>\n"
            
        if edit:
            # Remove the current entry from the list
            keptRecords = str(data[:index] + data[index+1:]).replace("'", '"')
            keptRecords = urllib.parse.quote(keptRecords)
            html_output += f"<td><a href='edit?dns={keptRecords}'>Remove</a></td>\n"

        html_output += "  </tr>\n"    
        index += 1
    return html_output

def txs(data):
    data = data[::-1]

    html_output = ""

    for entry in data:
        html_output += f"<tr><td>{entry['action']}</td>\n"
        html_output += f"<td><a target='_blank' href='{TX_EXPLORER_URL}{entry['txid']}'>{entry['txid'][:8]}...</a></td>\n"
        amount = entry['amount']
        amount = amount / 1000000

        if entry['blind'] == None:
            html_output += f"<td>{amount:,.2f} HNS</td>\n"
        else:
            blind = entry['blind']
            blind = blind / 1000000
            html_output += f"<td>{amount:,.2f} + {blind:,.2f} HNS</td>\n"

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
        html += "<tr>"
        html += f"<td>{lockup:,.2f} HNS</td>"
        revealed = False
        for reveal in reveals:
            if reveal['bid'] == bid['prevout']['hash']:
                revealed = True
                value = reveal['value']
                value = value / 1000000
                html += f"<td>{value:,.2f} HNS</td>"
                bidValue = lockup - value
                html += f"<td>{bidValue:,.2f} HNS</td>"                               
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


def bidDomains(bids,domains, sortbyDomains=False):
    html = ''

    if not sortbyDomains:
        for bid in bids:
            for domain in domains:
                if bid['name'] == domain['name']:
                    lockup = bid['lockup']
                    lockup = lockup / 1000000
                    bidValue = bid['value'] / 1000000
                    blind = lockup - bidValue

                    bidDisplay = f'<b>{bidValue:,.2f} HNS</b> + {blind:,.2f} HNS blind'
                    

                    html += "<tr>"
                    html += f"<td><a class='text-decoration-none' style='color: var(--bs-table-color-state, var(--bs-table-color-type, var(--bs-table-color)));' href='/auction/{domain['name']}'>{domain['name']}</a></td>"
                    html += f"<td>{domain['state']}</td>"
                    html += f"<td>{bidDisplay}</td>"
                    html += f"<td>{domain['height']:,}</td>"
                    html += "</tr>"
    else:
        for domain in domains:
            for bid in bids:
                if bid['name'] == domain['name']:
                    lockup = bid['lockup']
                    lockup = lockup / 1000000
                    bidValue = bid['value'] / 1000000
                    blind = lockup - bidValue

                    bidDisplay = f'<b>{bidValue:,.2f} HNS</b> + {blind:,.2f} HNS blind'
                    html += "<tr>"
                    html += f"<td><a class='text-decoration-none' style='color: var(--bs-table-color-state, var(--bs-table-color-type, var(--bs-table-color)));' href='/auction/{domain['name']}'>{domain['name']}</a></td>"
                    html += f"<td>{domain['state']}</td>"
                    html += f"<td>{bidDisplay}</td>"
                    html += f"<td>{domain['height']:,}</td>"
                    html += "</tr>"
    return html


def wallets(wallets):
    html = ''
    for wallet in wallets:
        html += f'<option value="{wallet}">{wallet}</option>'
    return html

def plugins(plugins):
    html = ''
    for plugin in plugins:
        name = plugin['name']
        link = plugin['link']

        if plugin['verified']:
            html += f'<li class="list-group-item"><a class="btn btn-secondary" style="width:100%;height:100%;margin:0px;font-size: x-large;" role="button" href="/plugin/{link}">{name}</a></li>'
        else:
            html += f'<li class="list-group-item"><a class="btn btn-danger" style="width:100%;height:100%;margin:0px;font-size: x-large;" role="button" href="/plugin/{link}">{name} (Not verified)</a></li>'
    return html

def plugin_functions(functions, pluginName):
    html = ''
    for function in functions:
        name = functions[function]['name']
        description = functions[function]['description']
        params = functions[function]['params']
        returnsRaw = functions[function]['returns']

        returns = ""
        for output in returnsRaw:
            returns += f"{returnsRaw[output]['name']}, "

        returns = returns.removesuffix(', ')

        functionType = "default"
        if "type" in functions[function]:
            functionType = functions[function]["type"]


        html += f'<div class="card" style="margin-top: 50px;">'
        html += f'<div class="card-body">'
        html += f'<h4 class="card-title">{name}</h4>'
        html += f'<h6 class="text-muted card-subtitle mb-2">{description}</h6>'
        html += f'<h6 class="text-muted card-subtitle mb-2">Function type: {functionType.capitalize()}</h6>'

        if functionType != "default":
            html += f'<p class="card-text">Returns: {returns}</p>'
            html += f'</div>'
            html += f'</div>'
            continue

        # Form
        html += f'<form method="post" style="padding: 20px;" action="/plugin/{pluginName}/{function}">'
        for param in params:
            html += f'<div style="margin-bottom: 20px;">'
            paramName = params[param]["name"]
            paramType = params[param]["type"]
            if paramType == "text":
                html += f'<label for="{param}">{paramName}</label>'
                html += f'<input class="form-control" type="text" name="{param}" />'
            elif paramType == "longText":
                html += f'<label for="{param}">{paramName}</label>'
                html += f'<textarea class="form-control" name="{param}" rows="4" cols="50"></textarea>'
            elif paramType == "number":
                html += f'<label for="{param}">{paramName}</label>'
                html += f'<input class="form-control" type="number" name="{param}" />'
            elif paramType == "checkbox":
                html += f'<div class="form-check"><input id="{param}" class="form-check-input" type="checkbox" name="{param}" /><label class="form-check-label" for="{param}">{paramName}</label></div>'
            elif paramType == "address":
                # render components/address.html
                address = render_template('components/address.html', paramName=paramName, param=param)
                html += address
            elif paramType == "dns":
                html += render_template('components/dns-input.html', paramName=paramName, param=param)


                
            
            html += f'</div>'
        
        html += f'<button type="submit" class="btn btn-primary">Submit</button>'        
        html += f'</form>'
        # For debugging
        html += f'<p class="card-text">Returns: {returns}</p>'
        html += f'</div>'
        html += f'</div>'
        
        
    return html

def plugin_output(outputs, returns):

    html = ''
    
    for returnOutput in returns:
        if returnOutput not in outputs:
            continue
        html += f'<div class="card" style="margin-top: 50px; margin-bottom: 50px;">'
        html += f'<div class="card-body">'
        html += f'<h4 class="card-title">{returns[returnOutput]["name"]}</h4>'
        
        output = outputs[returnOutput]
        if returns[returnOutput]["type"] == "list":
            html += f'<ul>'
            for item in output:
                html += f'<li>{item}</li>'
            html += f'</ul>'
        elif returns[returnOutput]["type"] == "text":
            html += f'<p>{output}</p>'
        elif returns[returnOutput]["type"] == "tx":
            html += render_template('components/tx.html', tx=output)
        elif returns[returnOutput]["type"] == "dns":
            output = json.loads(output)
            html += render_template('components/dns-output.html', dns=dns(output))


        html += f'</div>'
        html += f'</div>'        
    return html

def plugin_output_dash(outputs, returns):

    html = ''
    
    for returnOutput in returns:
        if returnOutput not in outputs:
            continue
        if outputs[returnOutput] == None:
            continue
        html += render_template('components/dashboard-plugin.html', name=returns[returnOutput]["name"], output=outputs[returnOutput])         
    return html