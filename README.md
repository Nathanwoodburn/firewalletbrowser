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

```bash
python3 server.py
# Or for more verbose output
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