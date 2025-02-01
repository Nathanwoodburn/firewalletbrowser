import dns.resolver
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import tempfile
import subprocess
import binascii
import datetime
import dns.asyncresolver
import httpx
from requests_doh import DNSOverHTTPSSession, add_dns_provider
import requests

def hip2(domain: str):
    domain_check = False
    try:        
        # Get the IP
        ip = resolve_with_doh(domain)
        
        # Run the openssl s_client command
        s_client_command = ["openssl","s_client","-showcerts","-connect",f"{ip}:443","-servername",domain,]

        s_client_process = subprocess.Popen(s_client_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        s_client_output, _ = s_client_process.communicate(input=b"\n")
        
        certificates = []
        current_cert = ""
        for line in s_client_output.split(b"\n"):
            current_cert += line.decode("utf-8") + "\n"
            if "-----END CERTIFICATE-----" in line.decode("utf-8"):
                certificates.append(current_cert)
                current_cert = ""

        # Remove anything before -----BEGIN CERTIFICATE-----
        certificates = [cert[cert.find("-----BEGIN CERTIFICATE-----"):] for cert in certificates]

        if certificates:
            cert = certificates[0]

            with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_cert_file:
                temp_cert_file.write(cert)
                temp_cert_file.seek(0)  # Move back to the beginning of the temporary file

            tlsa_command = ["openssl","x509","-in",temp_cert_file.name,"-pubkey","-noout","|","openssl","pkey","-pubin","-outform","der","|","openssl","dgst","-sha256","-binary",]
            
            tlsa_process = subprocess.Popen(" ".join(tlsa_command), shell=True, stdout=subprocess.PIPE)
            tlsa_output, _ = tlsa_process.communicate()

            tlsa_server = "3 1 1 " + binascii.hexlify(tlsa_output).decode("utf-8")


            # Get domains
            cert_obj = x509.load_pem_x509_certificate(cert.encode("utf-8"), default_backend())

            domains = []
            for ext in cert_obj.extensions:
                if ext.oid == x509.ExtensionOID.SUBJECT_ALTERNATIVE_NAME:
                    san_list = ext.value.get_values_for_type(x509.DNSName)
                    domains.extend(san_list)
            
            # Extract the common name (CN) from the subject
            common_name = cert_obj.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
            if common_name:
                if common_name[0].value not in domains:
                    domains.append(common_name[0].value)

            if domains:
                if domain in domains:
                    domain_check = True
                else:
                    # Check if matching wildcard domain exists
                    for d in domains:
                        if d.startswith("*"):
                            if domain.split(".")[1:] == d.split(".")[1:]:
                                domain_check = True
                                break
        

            expiry_date = cert_obj.not_valid_after
            # Check if expiry date is past
            if expiry_date < datetime.datetime.now():
                return "Hip2: Certificate is expired"


        else:
            return "Hip2: No certificate found"

        try:
            # Check for TLSA record
            tlsa = resolve_TLSA_with_doh(domain)
            

            if not tlsa:
                return "Hip2: TLSA lookup failed"
            else:
                if tlsa_server == str(tlsa):
                    if domain_check:
                        # Get the Hip2 addresss from /.well-known/wallets/HNS
                        add_dns_provider("HNSDoH", "https://hnsdoh.com/dns-query")

                        session = DNSOverHTTPSSession("HNSDoH")
                        r = session.get(f"https://{domain}/.well-known/wallets/HNS",verify=False)
                        return r.text
                    else:
                        return "Hip2: TLSA record matches certificate, but domain does not match certificate"
                
                else:
                    return "Hip2: TLSA record does not match certificate"
        
        except Exception as e:
            return "Hip2: TLSA lookup failed with error: " + str(e)


        
            
    # Catch all exceptions
    except Exception as e:
        print(f"Hip2: Lookup failed with error: {e}",flush=True)
        return "Hip2: Lookup failed."


def resolve_with_doh(query_name, doh_url="https://hnsdoh.com/dns-query"):
    with httpx.Client() as client:
        q = dns.message.make_query(query_name, dns.rdatatype.A)
        r = dns.query.https(q, doh_url, session=client)

        ip = r.answer[0][0].address
        return ip
    
def resolve_TLSA_with_doh(query_name, doh_url="https://hnsdoh.com/dns-query"):
    query_name = "_443._tcp." + query_name
    with httpx.Client() as client:
        q = dns.message.make_query(query_name, dns.rdatatype.TLSA)
        r = dns.query.https(q, doh_url, session=client)

        tlsa = r.answer[0][0]
        return tlsa


def niami_info(domain: str):
    response = requests.get(f"https://api.niami.io/hsd/{domain}")
    if response.status_code != 200:
        return False
    
    response = response.json()
    if response["data"]["owner_tx_data"] is not None:
        output = {
            "owner": response["data"]["owner_tx_data"]["address"]
        }
    else:
        output = {
            "owner": None
        }

    if 'dnsData' in response["data"]:
        output["dns"] = response["data"]["dnsData"]
    else:
        output["dns"] = []

    transactions = requests.get(f"https://api.niami.io/txs/{domain}")
    if transactions.status_code != 200:
        return False
    
    transactions = transactions.json()
    output["txs"] = transactions["txs"]
    return output

        
def emoji_to_punycode(emoji):
    try:
        return emoji.encode("idna").decode("ascii")
    except Exception as e:
        return emoji
    
def punycode_to_emoji(punycode):
    try:
        return punycode.encode("ascii").decode("idna")
    except Exception as e:
        return punycode