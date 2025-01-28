import json
import account
import requests

import dns.resolver
import dns.message
import dns.query
import dns.rdatatype
import dns.rrset
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import tempfile
import subprocess
import binascii
import datetime
import dns.asyncresolver
import httpx
from requests_doh import DNSOverHTTPSSession, add_dns_provider
import domainLookup

doh_url = "https://hnsdoh.com/dns-query"

# Plugin Data
info = {
    "name": "Troubleshooting",
    "description": "Various troubleshooting functions",
    "version": "1.0",
    "author": "Nathan.Woodburn/"
}

# Functions
functions = {
    "dig":{
        "name": "DNS Lookup",
        "type": "default",
        "description": "Do DNS lookups on a domain",
        "params": {
            "domain": {
                "name":"Domain to lookup (eg. woodburn)",
                "type":"text"
            },
            "type": {
                "name":"Type of lookup (A,TXT,NS,DS,TLSA)",
                "type":"text"
            }
        },
        "returns": {
            "result": 
            {
                "name": "Result",
                "type": "list"
            }
        }
    },
    "https_check":{
        "name": "HTTPS Check",
        "type": "default",
        "description": "Check if a domain has an HTTPS certificate",
        "params": {
            "domain": {
                "name":"Domain to lookup (eg. woodburn)",
                "type":"text"
            }
        },
        "returns": {
            "result": 
            {
                "name": "Result",
                "type": "text"
            }
        }
    },
    "hip_lookup": {
        "name": "Hip Lookup",
        "type": "default",
        "description": "Look up a domain's hip address",
        "params": {
            "domain": {
                "name": "Domain to lookup",
                "type": "text"
            }
        },
        "returns": {
            "result": {
                "name": "Result",
                "type": "text"
            }
        }
    }
}

def dns_request(domain: str, rType:str) -> list[dns.rrset.RRset]:
    if rType == "":
        rType = "A"
    rType = dns.rdatatype.from_text(rType.upper())


    with httpx.Client() as client:
        q = dns.message.make_query(domain, rType)
        r = dns.query.https(q, doh_url, session=client)
        return r.answer


def dig(params, authentication):
    domain = params["domain"]
    type = params["type"]
    result: list[dns.rrset.RRset] = dns_request(domain, type)
    print(result)
    if result:
        if len(result) == 1:
            result: dns.rrset.RRset = result[0]
            result = result.items
            return {"result": result}

        else:
            return {"result": result}
    else:
        return {"result": ["No result"]}
    


def https_check(params, authentication):
    domain = params["domain"]
    domain_check = False
    try:        
        # Get the IP
        ip = list(dns_request(domain,"A")[0].items.keys())
        if len(ip) == 0:
            return {"result": "No IP found"}
        ip = ip[0]
        print(ip)
        
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
            print(f"TLSA Server: {tlsa_server}")


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
                return {"result": "Certificate is expired"}
        else:
            return {"result": "No certificate found"}

        try:
            # Check for TLSA record
            tlsa = dns_request(f"_443._tcp.{domain}","TLSA")
            tlsa = list(tlsa[0].items.keys())
            if len(tlsa) == 0:
                return {"result": "No TLSA record found"}
            tlsa = tlsa[0]
            print(f"TLSA: {tlsa}")

            if not tlsa:
                return {"result": "TLSA lookup failed"}
            else:
                if tlsa_server == str(tlsa):
                    if domain_check:
                        add_dns_provider("HNSDoH", "https://hnsdoh.com/dns-query")

                        session = DNSOverHTTPSSession("HNSDoH")
                        r = session.get(f"https://{domain}/",verify=False)
                        if r.status_code != 200:
                            return {"result": "Webserver returned status code: " + str(r.status_code)}
                        return {"result": "HTTPS check successful"}
                    else:
                        return {"result": "TLSA record matches certificate, but domain does not match certificate"}
                
                else:
                    return {"result": "TLSA record does not match certificate"}
        
        except Exception as e:
            return {"result": "TLSA lookup failed with error: " + str(e)}

    # Catch all exceptions
    except Exception as e:
        return {"result": "Lookup failed.<br><br>Error: " + str(e)}
    
def hip_lookup(params, authentication):
    domain = params["domain"]
    hip = domainLookup.hip2(domain)
    return {"result": hip}