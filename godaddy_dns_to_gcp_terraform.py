"""Script to read DNS settings from GoDaddy Developer API, convert records to equivalent GCP DNS records, and output
a config file for use with Terraform."""
import argparse
import logging
from collections import defaultdict
from typing import Dict, List

import godaddy_dns

DEFAULT_OUTPUT_FILE = "migrated.tf"


def zone_url_to_name(zone_url):
    """Sanitize DNS zone for terraform resource names

    zone_url_to_name("mydomain.com.")
    >>> "mydomain-com"
    """
    return zone_url.rstrip(".").replace(".", "-")


def sanitize_tf_resource_name(name):
    """Sanitize concatenated name for terraform resource names"""
    return name.replace(".", "-").replace("_", "")


def terraform_zone_stanza(zone_url):
    """Declares GCP managed DNS Zone"""
    zone_name = zone_url_to_name(zone_url)

    return f"""
resource "google_dns_managed_zone" "{zone_name}" {{
  name = "{zone_name}"
  dns_name = "{zone_url}."
  description = "{zone_url} DNS zone. Managed by Terraform"

  visibility = "public"
}}
"""


def godaddy_to_url(godaddy_attr, zone_url, is_rrdatas=False, is_TXT_data=False, use_terraform_var=False):
    """ Convert name from GoDaddy record into url for GCP terraform.

    For example "subdomain.mydomain.com" or "subdomain.${google_dn_managed_zone.mydomain-com.dns_name}"

    Args:
        godaddy_name: value from godaddy record ("name" or "data" field)
        zone_url: url for output zone (e.g. "mydomain.es")
        is_rrdatas: will return value be used in rrdatas field?
        is_TXT_data: did entry original from TXT data value?
        use_terraform_var: use a Terraform variable for DNS zone url?  (If not, inline domain url directly)

    """
    if use_terraform_var:
        suffix = f"${{google_dns_managed_zone.{zone_url_to_name(zone_url)}.dns_name}}"
    else:
        suffix = zone_url

    # Godaddy usually specifies the website url as a prefix to the zone url.  When there is no prefix, they use "@"
    if godaddy_attr == "@":
        return suffix
    elif is_rrdatas:
        if is_TXT_data:
            return godaddy_attr
        else:
            return godaddy_attr + "."
    else:
        return ".".join([godaddy_attr, suffix])


def get_ttl(godaddy_records):
    """Warn user godaddy records for one type and name (e.g. "TXT" records for "subdomain.mydomain.com") have different TTLs"""
    unique_ttls = set([r["ttl"] for r in godaddy_records])
    ttl = list(unique_ttls)[0]
    if len(unique_ttls) > 1:
        logging.warning(f"Found multiple TTLs for following records.  Using {ttl}. {godaddy_records}")
    return ttl


def terraform_A_record_set(godaddy_records, zone_url):
    godaddy_name = godaddy_records[0]["name"]
    resource_name = sanitize_tf_resource_name(godaddy_to_url(godaddy_name, zone_url))
    url = godaddy_to_url(godaddy_name, zone_url, use_terraform_var=True)

    rrdata_strings = list(map(lambda r: f'"{r["data"]}",', godaddy_records))
    rrdatas_string = "[" + "\n\t".join(rrdata_strings) + "]"

    record_block = f"""
resource "google_dns_record_set" "{resource_name}-a" {{
    name = "{url}"
    managed_zone = google_dns_managed_zone.{zone_url_to_name(zone_url)}.name
    type = "A"
    ttl = {get_ttl(godaddy_records)}
    rrdatas = {rrdatas_string}
}}
"""
    return record_block


def terraform_CNAME_record_set(godaddy_records, zone_url):
    if len(godaddy_records) != 1:
        raise NotImplementedError("Not sure how to handle multiple CNAME records")
    godaddy_record = godaddy_records[0]
    godaddy_name = godaddy_record["name"]
    resource_name = sanitize_tf_resource_name(godaddy_to_url(godaddy_name, zone_url))
    url = godaddy_to_url(godaddy_name, zone_url, use_terraform_var=True)
    # TODO: bad suffix logic?
    target = godaddy_to_url(godaddy_record["data"], zone_url, is_rrdatas=True, use_terraform_var=True)

    record_block = f"""
resource "google_dns_record_set" "{resource_name}-cname" {{
    name = "{url}"
    managed_zone = google_dns_managed_zone.{zone_url_to_name(zone_url)}.name
    type = "CNAME"
    ttl = {godaddy_record['ttl']}
    rrdatas = ["{target}"]
}}
"""
    return record_block


def terraform_MX_record_set(godaddy_records, zone_url):
    godaddy_name = godaddy_records[0]["name"]
    resource_name = sanitize_tf_resource_name(godaddy_to_url(godaddy_name, zone_url))
    url = godaddy_to_url(godaddy_name, zone_url, use_terraform_var=True)

    priority_addresses = [(r["priority"], r["data"]) for r in godaddy_records]
    priority_addresses.sort(key=lambda pa: pa[0])  # inplace sort

    rrdata_strings = list(map(lambda pa: f'"{pa[0]} {pa[1]}.",', priority_addresses))
    rrdatas_string = "[" + "\n\t".join(rrdata_strings) + "]"

    record_block = f"""
resource "google_dns_record_set" "{resource_name}-mx" {{
    name = "{url}"
    managed_zone = google_dns_managed_zone.{zone_url_to_name(zone_url)}.name
    type = "MX"
    ttl = {get_ttl(godaddy_records)}
    rrdatas = {rrdatas_string}
}}
"""
    return record_block


def convert_data_for_TXT(orig_data):
    """handles string formatting specified in https://www.terraform.io/docs/providers/google/r/dns_record_set.html"""
    orig_data = f'\\"{orig_data}\\""'

    # for very long rrdatas, need to add quotes between each 255char substring
    idx = 0
    tgt = '"'
    while idx < len(orig_data):
        tgt += orig_data[idx : idx + 255]
        idx += 255
        if idx < len(orig_data):
            tgt += r"\" \""
    return tgt


def terraform_TXT_record_set(godaddy_records, zone_url):
    godaddy_name = godaddy_records[0]["name"]
    resource_name = sanitize_tf_resource_name(godaddy_to_url(godaddy_name, zone_url))
    url = godaddy_to_url(godaddy_name, zone_url, use_terraform_var=True)

    # Merge multiple TXT records using a comma (https://serverfault.com/a/1013575)
    target_strs = []
    for record in godaddy_records:
        target_str = convert_data_for_TXT(godaddy_to_url(record["data"], zone_url, is_rrdatas=True, is_TXT_data=True))
        target_strs.append(target_str)
    target = ",\n\t".join(target_strs)

    record_block = f"""
resource "google_dns_record_set" "{resource_name}-txt" {{
    name = "{url}"
    managed_zone = google_dns_managed_zone.{zone_url_to_name(zone_url)}.name
    type = "TXT"
    ttl = {get_ttl(godaddy_records)}
    rrdatas = [{target}]
}}
"""
    return record_block


def group_records_by_type_name(godaddy_records) -> Dict[str, Dict[str, List[Dict]]]:
    """
    Sorts godaddy DNS records into two layer dictionary:

    {
        'A': {'api.edison.merantix.com': [record_1, record_2]},
              'merantix.com': [record_1],...
              },
        'CNAME': {name: [record_1, ...
    }}

    """
    type_to_records = defaultdict(list)
    for record in godaddy_records:
        type_to_records[record["type"]].append(record)
    type_to_records = dict(type_to_records)

    type_to_name_to_records = dict()
    for record_type, records in type_to_records.items():
        name_to_records = defaultdict(list)
        for record in records:
            name_to_records[record["name"]].append(record)
        type_to_name_to_records[record_type] = dict(name_to_records)

    return type_to_name_to_records


def export_godaddy_dns_to_tf_file(zone_url: str, output_file: str = DEFAULT_OUTPUT_FILE):
    """
    Reads the DNS settings for godaddy_zone_url (e.g. "mydomain.com") and exports them to a Terraform file for use
    in a Google Cloud Project DNS Zone.

    Args:
        zone_url: DNS zone to migrate. (e.g. "mydomain.com")
        output_file: filepath to output terraform config
    """
    records = godaddy_dns.get_domain_dns_records(zone_url)
    type_to_name_to_records = group_records_by_type_name(records)

    with open(output_file, "w") as f:
        f.write(terraform_zone_stanza(zone_url))

        if "A" in type_to_name_to_records:
            for A_records in type_to_name_to_records["A"].values():
                f.write(terraform_A_record_set(A_records, zone_url))

        if "CNAME" in type_to_name_to_records:
            for CNAME_records in type_to_name_to_records["CNAME"].values():
                f.write(terraform_CNAME_record_set(CNAME_records, zone_url))

        if "MX" in type_to_name_to_records:
            for MX_records in type_to_name_to_records["MX"].values():
                f.write(terraform_MX_record_set(MX_records, zone_url))

        if "TXT" in type_to_name_to_records:
            for TXT_records in type_to_name_to_records["TXT"].values():
                f.write(terraform_TXT_record_set(TXT_records, zone_url))

    for record_type, name_to_records in type_to_name_to_records.items():
        # NOTE: ignore NS (Name Server) records because these are determined by GCP automatically and cannot be changed.
        if record_type not in ["A", "CNAME", "MX", "NS", "TXT"]:
            logging.warning(f"No logic for migrating record type {record_type}: {name_to_records}")

    logging.info(f"Wrote file {output_file}")


def main():
    logging.basicConfig(level=logging.INFO)

    # get domain name from command line
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", help="domain name to migrate (e.g. mydomain.com)", required=True)
    args = parser.parse_args()
    domain = args.domain

    logging.info(f"Migrating {domain}")
    export_godaddy_dns_to_tf_file(domain)


if __name__ == "__main__":
    main()
