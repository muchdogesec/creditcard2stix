import csv
import uuid
import json
import requests
import hashlib
import argparse
import logging
from datetime import datetime
from stix2 import Bundle, Identity, Relationship, CustomObservable, Report, parse, FileSystemStore
from stix2.properties import StringProperty, IDProperty, ListProperty, ReferenceProperty
from dotenv import load_dotenv
import os
import shutil

# Load API key from .env file
load_dotenv()
BIN_LIST_API_KEY = os.getenv("BIN_LIST_API_KEY")

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Define namespaces
OASIS_NAMESPACE = "00abedb4-aa42-466c-9c01-fed23315a9b7"
IDENTITY_NAMESPACE = "d287a5a4-facc-5254-9563-9e92e3e729ac"

# Define output directory
OUTPUT_DIR = "stix2_objects"

# URLs of default STIX objects
DEFAULT_OBJECT_URLS = [
    "https://raw.githubusercontent.com/muchdogesec/stix4doge/main/objects/extension-definition/bank-card.json",
    "https://raw.githubusercontent.com/muchdogesec/stix4doge/main/objects/identity/creditcard2stix.json",
    "https://raw.githubusercontent.com/muchdogesec/stix4doge/main/objects/marking-definition/creditcard2stix.json"
]

_type = 'bank-card'

@CustomObservable('bank-card', [
    ('type', StringProperty(fixed=_type)),
    ('spec_version', StringProperty(fixed='2.1')),
    ('id', IDProperty(_type, spec_version='2.1')),
    ('format', StringProperty()),
    ('number', StringProperty(required=True)),
    ('scheme', StringProperty()),
    ('brand', StringProperty()),
    ('currency', StringProperty()),
    ('issuer_name', StringProperty()),
    ('issuer_country', StringProperty()),
    ('holder_name', StringProperty()),
    ('valid_from', StringProperty()),
    ('valid_to', StringProperty()),
    ('security_code', StringProperty()),
], id_contrib_props=['number'])
class BankCard(object):
    pass

def get_bin_data(card_number):
    bin_number = card_number[:6]
    url = f"https://bin-ip-checker.p.rapidapi.com/?bin={bin_number}"
    headers = {
        'Content-Type': 'application/json',
        'x-rapidapi-host': 'bin-ip-checker.p.rapidapi.com',
        'x-rapidapi-key': BIN_LIST_API_KEY
    }
    try:
        logging.debug(f"Requesting BIN data for card number: {card_number}")
        response = requests.post(url, headers=headers, json={"bin": bin_number}, timeout=10)
        response.raise_for_status()
        logging.debug(f"Received response: {response.json()}")
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Error fetching BIN data for {card_number}: {e}")
        return None

def create_identity(bin_data):
    issuer = bin_data['BIN']['issuer']
    country = bin_data['BIN']['country']
    name = f"{issuer['name']} ({country['alpha2']})"
    identity_id = f"identity--{str(uuid.uuid5(uuid.UUID(IDENTITY_NAMESPACE), name))}"
    return Identity(
        id=identity_id,
        name=name,
        created="2020-01-01T00:00:00.000Z",
        modified="2020-01-01T00:00:00.000Z",
        identity_class="organization",
        sectors=["financial-services"],
        contact_information=f"* Bank URL: {issuer['website']},\n* Bank Phone: {issuer['phone']}",
        created_by_ref="identity--d287a5a4-facc-5254-9563-9e92e3e729ac",
        object_marking_refs=[
            "marking-definition--94868c89-83c2-464b-929b-a1a8aa3c8487",
            "marking-definition--d287a5a4-facc-5254-9563-9e92e3e729ac"
        ]
    )

def create_credit_card_stix(card_data, bin_data):
    card_id = f"bank-card--{str(uuid.uuid5(uuid.UUID(OASIS_NAMESPACE), card_data['card_number']))}"
    credit_card_data = {
        'type': 'bank-card',
        'spec_version': '2.1',
        'id': card_id,
        'format': bin_data['BIN']['type'] if bin_data else None,
        'number': card_data['card_number'],
        'scheme': bin_data['BIN']['scheme'] if bin_data else None,
        'brand': bin_data['BIN']['brand'] if bin_data else None,
        'currency': bin_data['BIN']['currency'] if bin_data else None,
        'issuer_name': bin_data['BIN']['issuer']['name'] if bin_data else None,
        'issuer_country': bin_data['BIN']['country']['alpha2'] if bin_data else None,
    }
    
    # Add optional fields if they are present and not empty
    optional_fields = ['card_holder_name', 'card_valid_date', 'card_expiry_date', 'card_security_code']
    field_mapping = {
        'card_holder_name': 'holder_name',
        'card_valid_date': 'valid_from',
        'card_expiry_date': 'valid_to',
        'card_security_code': 'security_code'
    }
    
    for field in optional_fields:
        if card_data.get(field):
            credit_card_data[field_mapping[field]] = card_data[field]
    
    credit_card = BankCard(**credit_card_data)
    return credit_card

def create_relationship(card_stix, identity_stix):
    relationship_id = f"relationship--{str(uuid.uuid5(uuid.UUID(IDENTITY_NAMESPACE), f'{card_stix.id}+{identity_stix.id}'))}"
    return Relationship(
        id=relationship_id,
        relationship_type="issued-by",
        created_by_ref="identity--d287a5a4-facc-5254-9563-9e92e3e729ac",
        created="2020-01-01T00:00:00.000Z",
        modified="2020-01-01T00:00:00.000Z",
        source_ref=card_stix.id,
        target_ref=identity_stix.id,
        object_marking_refs=[
            "marking-definition--94868c89-83c2-464b-929b-a1a8aa3c8487",
            "marking-definition--d287a5a4-facc-5254-9563-9e92e3e729ac"
        ]
    )

def download_default_objects(fs_store):
    for url in DEFAULT_OBJECT_URLS:
        response = requests.get(url)
        response.raise_for_status()
        obj = parse(response.text)
        fs_store.add(obj)

def process_csv(input_csv, fs_store):
    identities = {}
    cards = {}

    with open(input_csv, newline='') as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            card_number = row['card_number']
            logging.debug(f"Processing card number: {card_number}")

            # Check if the card already exists and replace if the new record has more information
            if card_number in cards:
                existing_row = cards[card_number]
                if sum(bool(x) for x in row.values()) > sum(bool(x) for x in existing_row.values()):
                    cards[card_number] = row
            else:
                cards[card_number] = row

    for card_number, card_data in cards.items():
        bin_data = get_bin_data(card_number)
        card_stix = create_credit_card_stix(card_data, bin_data)
        fs_store.add(card_stix)

        if bin_data and bin_data['BIN']['valid']:
            identity_key = f"{bin_data['BIN']['issuer']['name']}_{bin_data['BIN']['country']['alpha2']}"
            if identity_key not in identities:
                identity_stix = create_identity(bin_data)
                identities[identity_key] = identity_stix
                fs_store.add(identity_stix)
            relationship_stix = create_relationship(card_stix, identities[identity_key])
            fs_store.add(relationship_stix)

def create_report(report_csv, stix_objects):
    with open(report_csv, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        report_data = next(reader)

    # Validate required fields
    if 'name' not in report_data:
        raise ValueError("Report CSV must contain 'name' field")

    name = report_data['name']
    description = report_data.get('description')
    published_str = report_data.get('published', datetime.utcnow().isoformat() + 'Z')
    try:
        published = datetime.strptime(published_str, '%Y-%m-%d').isoformat() + 'Z'
    except ValueError:
        published = datetime.utcnow().isoformat() + 'Z'

    object_refs = [obj.id for obj in stix_objects if obj.type == 'bank-card']

    report_id = f"report--{uuid.uuid5(uuid.UUID(IDENTITY_NAMESPACE), hashlib.md5(open(report_csv, 'rb').read()).hexdigest())}"

    report = Report(
        type="report",
        spec_version="2.1",
        id=report_id,
        created_by_ref="identity--d287a5a4-facc-5254-9563-9e92e3e729ac",
        created=published,
        modified=published,
        name=name,
        description=description,
        published=published,
        report_types=["observed-data"],
        object_refs=object_refs
    )

    return report

def main():
    parser = argparse.ArgumentParser(description='Process credit card data and convert to STIX 2.1 format.')
    parser.add_argument('--input_csv', required=True, help='Input CSV file with credit card data')
    parser.add_argument('--report_csv', help='Input CSV file for the report')
    args = parser.parse_args()

    logging.info(f"Processing input CSV: {args.input_csv}")

    # Ensure the output directory is fresh
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    fs_store = FileSystemStore(OUTPUT_DIR)
    download_default_objects(fs_store)
    process_csv(args.input_csv, fs_store)

    stix_objects = list(fs_store.query())

    if args.report_csv:
        logging.info(f"Generating report from CSV: {args.report_csv}")
        report = create_report(args.report_csv, stix_objects)
        fs_store.add(report)
        stix_objects.append(report)

    # Collect all stored objects and create a bundle with a specific UUID
    sorted_objects = sorted(stix_objects, key=lambda x: x.id)
    objects_data = ''.join([obj.serialize() for obj in sorted_objects])
    bundle_id = f"bundle--{uuid.uuid5(uuid.UUID(IDENTITY_NAMESPACE), hashlib.md5(objects_data.encode()).hexdigest())}"

    bundle = Bundle(objects=sorted_objects, id=bundle_id)

    output_file = os.path.join(OUTPUT_DIR, 'credit-card-bundle.json')
    with open(output_file, 'w') as f:
        f.write(bundle.serialize(pretty=True))

    logging.info(f'STIX bundle written to {output_file}')

if __name__ == '__main__':
    main()
