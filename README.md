# FireWalletBrowser


## Installation

```bash
git clone https://github.com/Nathanwoodburn/firewalletbrowser.git
cd firewalletbrowser
python3 -m pip install -r requirements.txt
cp example.env .env
# Edit .env to include your HSD API key
```

## Usage

Make sure HSD is running then run the following commands:

```bash
python3 server.py
# Or for more verbose output
python3 main.py
```

Then access the wallet at http://localhost:5000