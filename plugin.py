import os
import json
import importlib
import sys
import hashlib
import subprocess


def listPlugins():
    plugins = []
    customPlugins = []
    for file in os.listdir("plugins"):
        if file.endswith(".py"):
            if file != "main.py":
                plugin = importlib.import_module("plugins."+file[:-3])
                if "info" not in dir(plugin):
                    continue
                details = plugin.info
                details["source"] = "built-in"
                details["link"] = f"plugins/{file[:-3]}"
                plugins.append(details)

    # Check for imported plugins
    if not os.path.exists("user_data/plugins.json"):
        with open("user_data/plugins.json", "w") as f:
            json.dump([], f)

    with open("user_data/plugins.json", "r") as f:
        importurls = json.load(f)

    for importurl in importurls:
        # Get only repo name
        importPath = importurl.split("/")[-1].removesuffix(".git")

        # Git clone into customPlugins/<importPath>
        if not os.path.exists(f"customPlugins/{importPath}"):
            if os.system(f"git clone {importurl} customPlugins/{importPath}") != 0:
                continue
        else:
            if os.system(f"cd customPlugins/{importPath} && git pull") != 0:
                continue
        
        # Import plugins from customPlugins/<importPath>
        for file in os.listdir(f"customPlugins/{importPath}"):
            if file.endswith(".py"):
                if file != "main.py":
                    plugin = importlib.import_module(f"customPlugins.{importPath}."+file[:-3])
                    if "info" not in dir(plugin):
                        continue
                    details = plugin.info
                    details["source"] = importPath
                    details["link"] = f"customPlugins/{importPath}/{file[:-3]}"
                    plugins.append(details)

    # Verify plugin signature
    signatures = []
    try:
        with open("user_data/plugin_signatures.json", "r") as f:
            signatures = json.load(f)
    except:
        # Write a new signatures file
        with open("user_data/plugin_signatures.json", "w") as f:
            json.dump(signatures, f)

    for plugin in plugins:
        # Hash the plugin file
        pluginHash = hashPlugin(plugin["link"])
        if pluginHash not in signatures:
            plugin["verified"] = False
        else:
            plugin["verified"] = True

    return plugins


def pluginExists(plugin: str):
    return os.path.exists(plugin+".py")


def verifyPlugin(plugin: str):
    signatures = []
    try:
        with open("user_data/plugin_signatures.json", "r") as f:
            signatures = json.load(f)
    except:
        # Write a new signatures file
        with open("user_data/plugin_signatures.json", "w") as f:
            json.dump(signatures, f)

    # Hash the plugin file
    pluginHash = hashPlugin(plugin)
    if pluginHash not in signatures:
        signatures.append(pluginHash)
        with open("user_data/plugin_signatures.json", "w") as f:
            json.dump(signatures, f)


def hashPlugin(plugin: str):
    BUF_SIZE = 65536
    sha256 = hashlib.sha256()
    with open(plugin+".py", 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha256.update(data)
    return sha256.hexdigest()


def getPluginData(pluginStr: str):
    plugin = importlib.import_module(pluginStr.replace("/","."))

    # Check if the plugin is verified
    signatures = []
    try:
        with open("user_data/plugin_signatures.json", "r") as f:
            signatures = json.load(f)
    except:
        # Write a new signatures file
        with open("user_data/plugin_signatures.json", "w") as f:
            json.dump(signatures, f)

    info = plugin.info
    info["source"] = "built-in"

    # Check if the plugin is in customPlugins
    if pluginStr.startswith("customPlugins"):
        # Get git url for dir
        url = subprocess.check_output(f"cd customPlugins/{pluginStr.split('/')[-2]} && git remote get-url origin", shell=True).decode("utf-8").strip()
        info["source"] = url
        



    # Hash the plugin file
    pluginHash = hashPlugin(pluginStr)
    if pluginHash not in signatures:
        info["verified"] = False
    else:
        info["verified"] = True

    return info


def getPluginFunctions(plugin: str):
    plugin = importlib.import_module(plugin.replace("/","."))
    return plugin.functions


def runPluginFunction(plugin: str, function: str, params: dict, authentication: str):
    plugin_module = importlib.import_module(plugin.replace("/","."))
    if function not in plugin_module.functions:
        return {"error": "Function not found"}

    if not hasattr(plugin_module, function):
        return {"error": "Function not found"}

    # Get the function object from the plugin module
    plugin_function = getattr(plugin_module, function)

    # Check if the function is in the signature list
    signatures = []
    try:
        with open("user_data/plugin_signatures.json", "r") as f:
            signatures = json.load(f)
    except:
        # Write a new signatures file
        with open("user_data/plugin_signatures.json", "w") as f:
            json.dump(signatures, f)

    # Hash the plugin file
    pluginHash = hashPlugin(plugin)
    if pluginHash not in signatures:
        return {"error": "Plugin not verified"}

    # Call the function with provided parameters
    try:
        result = plugin_function(params, authentication)
        return result
    except Exception as e:
        print(f"Error running plugin: {e}")
        return {"error": str(e)}
    # return plugin.runFunction(function, params, authentication)


def getPluginFunctionInputs(plugin: str, function: str):
    plugin = importlib.import_module(plugin.replace("/","."))
    return plugin.functions[function]["params"]


def getPluginFunctionReturns(plugin: str, function: str):
    plugin = importlib.import_module(plugin.replace("/","."))
    return plugin.functions[function]["returns"]


def getDomainFunctions():
    plugins = listPlugins()
    domainFunctions = []
    for plugin in plugins:
        functions = getPluginFunctions(plugin["link"])
        for function in functions:
            if functions[function]["type"] == "domain":
                domainFunctions.append({
                    "plugin": plugin["link"],
                    "function": function,
                    "description": functions[function]["description"]
                })
    return domainFunctions


def getSearchFunctions():
    plugins = listPlugins()
    searchFunctions = []
    for plugin in plugins:
        functions = getPluginFunctions(plugin["link"])
        for function in functions:
            if functions[function]["type"] == "search":
                searchFunctions.append({
                    "plugin": plugin["link"],
                    "function": function,
                    "description": functions[function]["description"]
                })
    return searchFunctions


def getDashboardFunctions():
    plugins = listPlugins()
    dashboardFunctions = []
    for plugin in plugins:
        functions = getPluginFunctions(plugin["link"])
        for function in functions:
            if functions[function]["type"] == "dashboard":
                dashboardFunctions.append({
                    "plugin": plugin["link"],
                    "function": function,
                    "description": functions[function]["description"]
                })
    return dashboardFunctions
