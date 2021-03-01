"""
Retrieve GoDaddy DNS settings via their developer API

See also:
    https://developer.godaddy.com/doc/endpoint/domains#/
"""
import os
import time
from pprint import pprint
from typing import List

import requests

import credential_loaders

BASE_URL = "https://api.godaddy.com"

# You can easily replace these with a different CredentialLoader to match your key management system
API_KEY_CRED_LOADER = credential_loaders.EnvVarCredentialLoader("GODADDY_API_KEY")
API_SECRET_CRED_LOADER = credential_loaders.EnvVarCredentialLoader("GODADDY_API_SECRET")
# API_KEY_CRED_LOADER = credential_loaders.PlaintextCredentialLoader("./api_key.txt")
# API_SECRET_CRED_LOADER = credential_loaders.PlaintextCredentialLoader("./api_secret.txt")



def _get_headers() -> dict:
    """Get authorization header for GoDaddy Developer API.

    https://developer.godaddy.com/keys
    """
    api_key = API_KEY_CRED_LOADER.load_credentials()
    api_secret = API_SECRET_CRED_LOADER.load_credentials()
    return {"Authorization": "sso-key {}:{}".format(api_key, api_secret)}


def _call_endpoint(url_suffix: str, base_url: str = BASE_URL) -> dict:
    """Call GoDaddy developer API endpoint.

    Only supports GET endpoints to keep access read-only.
    """
    headers = _get_headers()
    url = os.path.join(base_url, url_suffix)
    resp = requests.get(url, headers=headers)
    return resp.json()


def get_domains() -> List[str]:
    """Get list of Domains for this API key."""
    ret = _call_endpoint("v1/domains")
    # Example response:
    # [{'createdAt': '2016-06-25T03:08:44.000Z',
    #  'domain': 'mydomain.com',
    #  'domainId': 12345678,
    #  'expirationProtected': False,
    #  'expires': '2020-06-25T03:08:44.000Z',
    #  'holdRegistrar': False,
    #  'locked': True,
    #  'nameServers': None,
    #  'privacy': False,
    #  'renewAuto': True,
    #  'renewDeadline': '2020-08-09T03:08:44.000Z',
    #  'renewable': True,
    #  'status': 'ACTIVE',
    #  'transferProtected': False},]
    domains = [d["domain"] for d in ret]
    return domains


def get_domain_dns_records(domain):
    """Get DNS entries for a specific domain

    Returns:
        List with format (for example):
        [ {'data': '160.153.162.20', 'name': '_dmarc', 'ttl': 3600, 'type': 'A'},
          {'data': 'ns37.domaincontrol.com', 'name': '@', 'ttl': 3600, 'type': 'NS'}, ...]
    """
    url_suffix = "v1/domains/{}/records".format(domain)
    ret = _call_endpoint(url_suffix)
    if isinstance(ret, dict) and ret.get('code', None) == "UNKNOWN_DOMAIN":
        # e.g. {'code': 'UNKNOWN_DOMAIN', 'message': 'The given domain is not registered, or does not have a zone file'}
        raise Exception(f"Can't find domain {domain}.  Are you sure your API key and secret are correct?: {ret}")
    return ret


def print_all_dns_records():
    """ Print each domain and its DNS records (for domains linked to this API key)."""
    for domain in sorted(get_domains()):
        dns_records = get_domain_dns_records(domain)
        print(domain)
        pprint(dns_records)
        print("*" * 50)
        # TODO: poor man's rate limiter.  improve?
        time.sleep(2)


if __name__ == "__main__":
    print_all_dns_records()
