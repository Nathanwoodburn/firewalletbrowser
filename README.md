# FireWalletBrowser


## Installation

```bash
git clone https://github.com/Nathanwoodburn/firewalletbrowser.git
cd firewalletbrowser
python3 -m pip install -r requirements.txt
cp example.env .env
```

Edit .env to have your HSD api key.
If you have HSD runnning on a separate computer also add the IP here

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
sudo docker run --network=host -e hsd_api=yourapikeyhere git.woodburn.au/nathanwoodburn/firewallet:latest
```

If you have HSD running on a different IP/container

```bash
sudo docker run -p 5000:5000 -e hsd_api=yourapikeyhere -e hsd_ip=hsdcontainer git.woodburn.au/nathanwoodburn/firewallet:latest
```

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
- Custom plugin support

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