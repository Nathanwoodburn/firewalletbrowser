# FireWalletBrowser
## Installation

See [here](https://firewallet.au/setup) for instructions on how to setup a FireWallet

```bash
git clone https://github.com/Nathanwoodburn/firewalletbrowser.git
cd firewalletbrowser
python3 -m pip install -r requirements.txt
cp example.env .env
```

Edit .env to have your HSD api key.
If you have HSD runnning on a separate computer also add the IP here

For a quick and easy installation on ubuntu/debian you can run the install.sh script
```bash
curl https://git.woodburn.au/nathanwoodburn/firewalletbrowser/raw/branch/main/install.sh | bash
```
This will install all dependencies (including Node/NPM for an internal HSD node), create a python virtual environment and install the required python packages.  
After the script has run you can start the wallet with
```bash
./start.sh
```


## Usage

Make sure HSD is running then run the following commands:

On Linux:
```bash
python3 server.py
# Or for more verbose output
python3 main.py
```

On Windows:
```bash
python3 main.py
```


Then access the wallet at http://localhost:5000


Also available as a docker image:
To run using a HSD running directly on the host:

```bash
sudo docker run --network=host -e HSD_API=yourapikeyhere git.woodburn.au/nathanwoodburn/firewallet:latest
```

If you have HSD running on a different IP/container

```bash
sudo docker run -p 5000:5000 -e HSD_API=yourapikeyhere -e HSD_IP=hsdcontainer git.woodburn.au/nathanwoodburn/firewallet:latest
```

For Docker you can mount a volume to persist the user data (/app/user_data)

## Features
- Basic wallet functionality
  - Create new wallet
  - Import wallet from seed
  - Send HNS
  - Receive HNS
  - Have multiple wallets
  - View transactions
  - View balance
  - View wallet domains
- Domain management
  - Transfer domains
  - DNS Editor
  - Renew domains
- Auctions
  - Send open
  - Send bid
  - Send reveal
  - Send redeem
- Download a list of all domains
- Resend all pending transactions
- Rescan
- Zap pending transactions
- View xPub
- Custom plugin support (find some [here](https://git.woodburn.au/nathanwoodburn?tab=repositories&q=plugin&sort=recentupdate))

## Themes
Set a theme in the .env file  
**Available themes**  
- dark-purple
- black

## Images
Login page  
![Login page](assets/login.png)

Home page  
![Home page](assets/home.png)

Transactions page  
![Transactions page](assets/transactions.png)

Send page  
![Send page](assets/send.png)

Transaction confirmation  
![Confirmation page](assets/confirmation.png)

Receive page  
![Receive page](assets/receive.png)

Settings page  
![Settings page](assets/settings.png)

Domain page  
![Domain page](assets/domain.png)

Domain management page  
![Domain management page](assets/domainmanage.png)

DNS Editor page
![DNS Editor page](assets/dnseditor.png)

Auction page
![Auction page](assets/auction.png)

## Environment variables

```yaml
HSD_API: HSD API key
HSD_IP: HSD IP address
THEME: Theme to use (dark-purple, black)
SHOW_EXPIRED: Show expired domains (true/false)
EXCLUDE: Comma separated list of wallets to exclude from the wallet list (default primary)
EXPLORER_TX: URL for exploring transactions (default https://shakeshift.com/transaction/)
HSD_NETWORK: Network to connect to (main, regtest, simnet)
DISABLE_WALLETDNS: Disable Wallet DNS records when sending HNS to domains (true/false)
INTERNAL_HSD: Use internal HSD node (true/false)
```



# Internal HSD

If you set INTERNAL_HSD=true in the .env file the wallet will start and manage its own HSD node. If you want to override the default HSD config create a file called hsdconfig.json in the same directory as main.py and change the values you want to override. For example to disable SPV and use an existing bob wallet sync (on linux) and set the agent to "SuperCoolDev" you could use the following:
```json
{
    "spv": false,
    "prefix":"~/.config/Bob/hsd_data",
    "flags":[
        "--agent=SuperCoolDev"
    ]
}
```

Supported config options are:
```yaml
spv: true/false
prefix: path to hsd data directory
flags: list of additional flags to pass to hsd
version: version of hsd to use (used when installing HSD from source)
chainMigrate: <int> (for users migrating from older versions of HSD)
walletMigrate: <int> (for users migrating from older versions of HSD)
```

## Support the Project

If you find FireWallet useful and would like to support its continued development, please consider making a donation. Your contributions help maintain the project and develop new features.

HNS donations can be sent to: `hs1qh7uzytf2ftwkd9dmjjs7az9qfver5m7dd7x4ej`
Other donation options can be found at [my website](https://nathan.woodburn.au/donate)

Thank you for your support!

## Warnings

- This is a work in progress and is not guaranteed to work
- This is not a wallet by itself but rather a frontend for HSD
- I am not responsible for any loss of funds from using this wallet (including loss of funds from auctions)
- I am not responsible if you expose this frontend to the internet (please don't do this unless you know what you are doing)