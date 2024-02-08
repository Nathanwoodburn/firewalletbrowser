import os
import json
import importlib



def listPlugins():
    plugins = []
    for file in os.listdir("plugins"):
        if file.endswith(".py"):
            if file != "main.py":
                plugin = importlib.import_module("plugins."+file[:-3])
                details = plugin.info
                details["link"] = file[:-3]
                plugins.append(details)

    # Verify plugin signature
    signatures = []
    try:
        with open("plugins/signatures.json", "r") as f:
            signatures = json.load(f)
    except:
        # Write a new signatures file
        with open("plugins/signatures.json", "w") as f:
            json.dump(signatures, f)
    
    for plugin in plugins:
        # Hash the plugin file
        with open(f"plugins/{plugin['link']}.py", "r") as f:
            file = f.read()
            plugin_hash = hash(file)
            if plugin_hash not in signatures:
                plugin["verified"] = False
            else:
                plugin["verified"] = True

    return plugins


def pluginExists(plugin: str):
    for file in os.listdir("plugins"):
        if file == plugin+".py":
            return True
    return False

def verifyPlugin(plugin: str):
    signatures = []
    try:
        with open("plugins/signatures.json", "r") as f:
            signatures = json.load(f)
    except:
        # Write a new signatures file
        with open("plugins/signatures.json", "w") as f:
            json.dump(signatures, f)

    # Hash the plugin file
    with open(f"plugins/{plugin}.py", "r") as f:
        file = f.read()
        plugin_hash = hash(file)
        if plugin_hash not in signatures:
            signatures.append(plugin_hash)
            with open("plugins/signatures.json", "w") as f:
                json.dump(signatures, f)

def getPluginData(pluginStr: str):
    plugin = importlib.import_module("plugins."+pluginStr)

    # Check if the plugin is verified
    signatures = []
    try:
        with open("plugins/signatures.json", "r") as f:
            signatures = json.load(f)
    except:
        # Write a new signatures file
        with open("plugins/signatures.json", "w") as f:
            json.dump(signatures, f)

    info = plugin.info
    # Hash the plugin file
    with open(f"plugins/{pluginStr}.py", "r") as f:
        file = f.read()
        plugin_hash = hash(file)
        if plugin_hash not in signatures:
            info["verified"] = False
        else:
            info["verified"] = True
            
    return info 

def getPluginFunctions(plugin: str):
    plugin = importlib.import_module("plugins."+plugin)
    return plugin.functions

def runPluginFunction(plugin: str, function: str, params: dict, authentication: str):
    plugin_module = importlib.import_module("plugins."+plugin)
    if function not in plugin_module.functions:
        return {"error": "Function not found"}
    
    if not hasattr(plugin_module, function):
        return {"error": "Function not found"}

    # Get the function object from the plugin module
    plugin_function = getattr(plugin_module, function)

    # Check if the function is in the signature list
    signatures = []
    try:
        with open("plugins/signatures.json", "r") as f:
            signatures = json.load(f)
    except:
        # Write a new signatures file
        with open("plugins/signatures.json", "w") as f:
            json.dump(signatures, f)

    # Hash the plugin file
    with open(f"plugins/{plugin}.py", "r") as f:
        file = f.read()
        plugin_hash = hash(file)
        if plugin_hash not in signatures:
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
    plugin = importlib.import_module("plugins."+plugin)
    return plugin.functions[function]["params"]

def getPluginFunctionReturns(plugin: str, function: str):
    plugin = importlib.import_module("plugins."+plugin)
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