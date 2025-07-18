import datetime
import json
import urllib.parse
from flask import render_template
from domainLookup import punycode_to_emoji
import os
from handywrapper import api
import threading

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

hsd = api.hsd(HSD_API, HSD_IP, HSD_NODE_PORT)

# Get Explorer URL
TX_EXPLORER_URL = os.getenv("EXPLORER_TX")
if TX_EXPLORER_URL is None:
    TX_EXPLORER_URL = "https://shakeshift.com/transaction/"


NAMEHASH_CACHE = 'user_data/namehash_cache.json'
# Validate cache version
if os.path.exists(NAMEHASH_CACHE):
    with open(NAMEHASH_CACHE, 'r') as f:
        cache = json.load(f)
    if not isinstance(cache, dict):
        print("Invalid namehash cache format. Resetting cache.")
        with open(NAMEHASH_CACHE, 'w') as f:
            json.dump({}, f)
    # Check if cache entries are valid
    for key in cache:
        if not cache[key].startswith("<a href='/manage/"):
            print(f"Invalid cache entry for {key}. Resetting cache.")
            with open(NAMEHASH_CACHE, 'w') as f:
                json.dump({}, f)
            break



CACHE_LOCK = threading.Lock()


HNS_ICON = '<img src="/assets/img/HNS.png" width="20px" style="filter: invert(1);" />'

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
        name = renderDomain(domain['name'])


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


actionMap = {
    "UPDATE": "Updated ",
    "REGISTER": "Registered ",
    "RENEW": "Renewed ",
    "BID": "Bid on ",
    "REVEAL": "Revealed bid for ",
    "REDEEM": "Redeemed bid for ",
    "TRANSFER": "Started transfer for ",
    "NONE": "Multiple actions"
}

actionMapPlural = {
    "UPDATE": "Updated multiple domains' records",
    "REGISTER": "Registered multiple domains",
    "RENEW": "Renewed multiple domains",
    "BID": "Bid on multiple domains",
    "REVEAL": "Revealed multiple bids",
    "REDEEM": "Redeemed multiple bids",
    "TRANSFER": "Started multiple domain transfers",
    "NONE": "Multiple actions"
}

def transactions(txs):
    
    if len(txs) == 0:
        return '<tr><td colspan="5">No transactions found</td></tr>'
    html = ''
    for tx in txs:
        action = "HNS Transfer"
        txhash = tx["hash"]        
        confirmations=tx["confirmations"]
        mined_date = "Pending"
        if confirmations >= 1:
            mined_date = tx["mdate"]
            if mined_date is None:
                mined_date = "Pending"
            else:
                # Format 2025-06-27T01:49:14Z
                mined_date = datetime.datetime.strptime(mined_date, "%Y-%m-%dT%H:%M:%SZ").strftime("%d %b %Y")
        incomming = True
        amount = 0
        bid_value = 0
        isMulti = 0
        nameHashes = []
        
        for txInput in tx["inputs"]:
            if txInput["path"]:
                incomming = False
                amount -= txInput["value"]

        for output in tx["outputs"]:
            if output["covenant"]["action"] != "NONE":
                if action == "HNS Transfer":
                    action = output["covenant"]["action"]
                elif action == output["covenant"]["action"]:
                    isMulti += 1
                else:
                    action = "Multiple Actions"
        
            
            if output["covenant"]["items"] and len(output["covenant"]["items"]) > 0:
                nameHashes.append(output["covenant"]["items"][0])

            if not incomming:
                if output["path"]:
                    amount += output["value"]
            else:
                if output["path"] and output["covenant"]["action"] == "NONE":
                    amount += output["value"]

            # Check if this is a bid
            if output["covenant"]["action"] == "BID":
                bid_value += output["value"]
                amount -= output["value"]

        if not incomming:
            # Subtract fee to make it easier to read
            amount += tx["fee"]


        amount = amount / 1000000
        bid_value = bid_value / 1000000
        humanAction = action

        if action == "HNS Transfer":
            if amount >= 0:
                humanAction = f"Received {amount:,.2f} {HNS_ICON}"
            else:
                humanAction = f"Sent {(amount*-1):,.2f} {HNS_ICON}"
        elif action == "FINALIZE":
            if incomming and not isMulti:
                humanAction = f"Received {renderFromNameHash(nameHashes[0])}"                    
            elif incomming and isMulti:
                humanAction = f"Received {isMulti + 1} domains"
            elif not isMulti:
                humanAction = f"Finalized {renderFromNameHash(nameHashes[0])}"
            else:
                humanAction = f"Finalized  {isMulti + 1} domain transfers"
        elif action == "BID" and not isMulti:
            humanAction = f"Bid {bid_value:,.2f} {HNS_ICON} on {renderFromNameHash(nameHashes[0])}"
        elif isMulti:
            humanAction = actionMapPlural.get(action, "Unknown Action")
            humanAction = humanAction.replace("multiple", f'{isMulti + 1}')
        else:
            humanAction  = actionMap.get(action, "Unknown Action")
            humanAction += renderFromNameHash(nameHashes[0])


        if amount < 0:
            amount = f"<span style='color: red;'>{amount:,.2f}</span>"
        elif amount > 0:
            amount = f"<span style='color: green;'>+{amount:,.2f}</span>"
        else:
            amount = f"<span style='color: gray;'>0.00</span>"


        # hash = f"<a target='_blank' href='{TX_EXPLORER_URL}{hash}'>{hash[:8]}...</a>"
        txdate = ""
        if confirmations < 5:
            txdate = f"<span style='color: red;'>{mined_date}</span>"
        else:
            txdate = f"<span>{mined_date}</span>"
            # confirmations = f"<td class='hide-mobile'>{confirmations:,}</td>"
        html += f'''
        <tr>
            <td style='white-space: nowrap;'>{txdate}</td>
            <td><a style="color:var(--bs-body-color); text-decoration:none;" target="_blank" href="{TX_EXPLORER_URL}{txhash}">{humanAction}</a></td>                        
        </tr>
        '''
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
                        if len(value) > 1:
                            html_output += '<td style="white-space: pre-wrap; font-family: monospace;">\n'
                            for val in value:
                                html_output += f"{val}<br>\n"
                            html_output += "</td>\n"
                        else:
                            html_output += f'<td style="white-space: pre-wrap; font-family: monospace;">{value[0]}</td>\n'
                    else:
                        html_output += f'<td style="white-space: pre-wrap; font-family: monospace;">{value}</td>\n'

        elif entry['type'] == 'DS':
            ds = f"{entry['keyTag']} {entry['algorithm']} {entry['digestType']} {entry['digest']}"
            html_output += f'<td style="white-space: pre-wrap; font-family: monospace;">{ds}</td>\n'

        else:
            value = ""
            for key, val in entry.items():
                if key != 'type':
                    value += f'{val} '
            html_output += f'<td style="white-space: pre-wrap; font-family: monospace;">{value.strip()}</td>\n'
            
        if edit:
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
    # Create a list to hold bid data for sorting
    bid_data = []
    
    # Prepare data for sorting
    for bid in bids:
        lockup = bid['lockup'] / 1000000
        revealed = False
        value = 0
        
        # Check if this bid has been revealed
        for reveal in reveals:
            if reveal['bid'] == bid['prevout']['hash']:
                revealed = True
                value = reveal['value'] / 1000000
                break
        
        # Store all relevant information for sorting and display
        bid_data.append({
            'bid': bid,
            'lockup': lockup,
            'revealed': revealed,
            'value': value,
            'sort_value': value if revealed else lockup  # Use value for sorting if revealed, otherwise lockup
        })
    # Sort by the sort_value in descending order (highest first)
    bid_data.sort(key=lambda x: x['sort_value'], reverse=True)
    
    # Generate HTML from sorted data
    html = ''
    for data in bid_data:
        bid = data['bid']
        lockup = data['lockup']
        revealed = data['revealed']
        value = data['value']
        
        html += "<tr>"
        html += f"<td>{lockup:,.2f} HNS</td>"
        
        if revealed:
            bidValue = lockup - value
            html += f"<td>{value:,.2f} HNS</td>"
            html += f"<td>{bidValue:,.2f} HNS</td>"
        else:
            html += f"<td>Hidden until reveal</td>"
            html += f"<td>Hidden until reveal</td>"
            
        if bid['own']:
            html += "<td>You</td>"
        else:
            html += f"<td>Unknown</td>"

        html += f"<td><a class='text-decoration-none' style='color: var(--bs-table-color-state, var(--bs-table-color-type, var(--bs-table-color)));' target='_blank' href='{TX_EXPLORER_URL}{bid['prevout']['hash']}'>Bid TX 🔗</a></td>"
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

                    if blind > 0:
                        bidDisplay = f'<b>{bidValue:,.2f}</b> (+{blind:,.2f}) HNS'
                    else:
                        bidDisplay = f'<b>{bidValue:,.2f}</b> HNS'
                    

                    html += "<tr>"
                    html += f"<td><a class='text-decoration-none' style='color: var(--bs-table-color-state, var(--bs-table-color-type, var(--bs-table-color)));' href='/auction/{domain['name']}'>{renderDomain(domain['name'])}</a></td>"
                    html += f"<td>{domain['state']}</td>"
                    html += f"<td style='white-space: nowrap;'>{bidDisplay}</td>"
                    html += f"<td class='hide-mobile'>{domain['height']:,}</td>"
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
                    html += f"<td><a class='text-decoration-none' style='color: var(--bs-table-color-state, var(--bs-table-color-type, var(--bs-table-color)));' href='/auction/{domain['name']}'>{renderDomain(domain['name'])}</a></td>"
                    html += f"<td>{domain['state']}</td>"
                    html += f"<td>{bidDisplay}</td>"
                    html += f"<td class='hide-mobile'>{domain['height']:,}</td>"
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


    except Exception as e:
        return f"{name}/"

def renderDomainAsync(namehash: str) -> None:
    """
    Get the domain name from HSD using its name hash and store it in the cache.
    This function is meant to be run in the background.
    """
    try:
        with CACHE_LOCK:
            if not os.path.exists(NAMEHASH_CACHE):
                with open(NAMEHASH_CACHE, 'w') as f:
                    json.dump({}, f)
            with open(NAMEHASH_CACHE, 'r') as f:
                cache = json.load(f)

            if namehash in cache:
                return

        # Fetch the name outside the lock (network call)
        name = hsd.rpc_getNameByHash(namehash)
        if name["error"] is None:
            name = name["result"]
            rendered = renderDomain(name)
            rendered = f"<a href='/manage/{name}' target='_blank' style='color: var(--bs-table-color-state, var(--bs-table-color-type, var(--bs-table-color)));'>{rendered}</a>"


            with CACHE_LOCK:
                with open(NAMEHASH_CACHE, 'r') as f:
                    cache = json.load(f)
                cache[namehash] = rendered
                with open(NAMEHASH_CACHE, 'w') as f:
                    json.dump(cache, f)

            return rendered
        else:
            print(f"Error fetching name for hash {namehash}: {name['error']}", flush=True)

    except Exception as e:
        print(f"Exception fetching name for hash {namehash}: {e}", flush=True)


def renderFromNameHash(nameHash: str) -> str:
    """
    Render a domain name from its name hash.
    Try to retrieve the name from the cache. If not, create a background task to fetch it.
    """
    try:
        with CACHE_LOCK:
            if not os.path.exists(NAMEHASH_CACHE):
                with open(NAMEHASH_CACHE, 'w') as f:
                    json.dump({}, f)
            with open(NAMEHASH_CACHE, 'r') as f:
                cache = json.load(f)

            if nameHash in cache:
                return cache[nameHash]
        thread = threading.Thread(target=renderDomainAsync, args=(nameHash,))
        thread.start()
        return "domain"

    except Exception as e:
        print(f"Exception in renderFromNameHash: {e}", flush=True)
        return "domain"