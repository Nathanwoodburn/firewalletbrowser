# Plugins

## Types
### Default
Type: `default`
This is the default type and is used when no type is specified.  
This type is displayed in the plugin page only.  
This is the onlu type of plugin that takes user input

### Manage & Search
For manage page use type: `domain`
For search page use type: `search`

This type is used for domain plugins. It shows in the manage domain page or the search page.
It gets the `domain` paramater as the only input (in addition to authentication)

### Dashboard
This type is used for dashboard plugins.
It shows in the dashboard page. It doesn't get any inputs other than the authentication


## Inputs

### Plain Text
Type: `text`

### Long Text
Type: `longText`

### Number
Type: `number`


### Checkbox
Type: `checkbox`

### Address
Type: `address`
This will handle hip2 resolution for you so the function will always receive a valid address

### DNS
Type: `dns`
This isn't done yet but use it over text as it includes parsing



## Outputs
### Plain Text
Type: `text`


### List
Type: `list`
This is a list if text items (or HTML items)

### Transaction hash
Type: `tx`
This will display the hash and links to explorers

### DNS records
Type: `dns`
This will display DNS in a table format
