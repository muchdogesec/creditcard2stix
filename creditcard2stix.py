import csv
import uuid
import json
import requests
import hashlib
import argparse
import logging
from datetime import datetime
from stix2 import Bundle, Identity, Relationship, FileSystemStore, CustomObservable
from stix2.properties import StringProperty, IDProperty, ListProperty, ReferenceProperty
from dotenv import load_dotenv
import os

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
    ('object_marking_refs', ListProperty(ReferenceProperty(valid_types='marking-definition', spec_version='2.1'))),
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
    credit_card = BankCard(
        type='bank-card',
        spec_version='2.1',
        id=card_id,
        format=bin_data['BIN']['type'] if bin_data else None,
        number=card_data['card_number'],
        scheme=bin_data['BIN']['scheme'] if bin_data else None,
        brand=bin_data['BIN']['brand'] if bin_data else None,
        currency=bin_data['BIN']['currency'] if bin_data else None,
        issuer_name=bin_data['BIN']['issuer']['name'] if bin_data else None,
        issuer_country=bin_data['BIN']['country']['alpha2'] if bin_data else None,
        holder_name=card_data.get('card_holder_name'),
        valid_from=card_data.get('card_valid_date'),
        valid_to=card_data.get('card_expiry_date'),
        security_code=card_data.get('card_security_code'),
        object_marking_refs=[
            "marking-definition--94868c89-83c2-464b-929b-a1a8aa3c8487",
            "marking-definition--d287a5a4-facc-5254-9563-9e92e3e729ac"
        ]
    )
    return credit_card

def create_relationship(card_stix, identity_stix):
    relationship_id = f"relationship--{str(uuid.uuid5(uuid.UUID(IDENTITY_NAMESPACE), f'{card_stix.id}+{identity_stix.id}'))}"
    return Relationship(
        id=relationship_id,
        relationship_type="issued-by",
        created_by_ref="identity--d287a5a4-facc-5254-9563-9e92e3e729ac",
        source_ref=card_stix.id,
        target_ref=identity_stix.id,
        object_marking_refs=[
            "marking-definition--94868c89-83c2-464b-929b-a1a8aa3c8487",
            "marking-definition--d287a5a4-facc-5254-9563-9e92e3e729ac"
        ]
    )

def process_csv(input_csv, fs_store):
    with open(input_csv, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        identities = {}
        
        for row in reader:
            card_number = row['card_number']
            logging.debug(f"Processing card number: {card_number}")
            bin_data = get_bin_data(card_number)
            card_stix = create_credit_card_stix(row, bin_data)
            fs_store.add(card_stix)
            
            if bin_data and bin_data['BIN']['valid']:
                identity_key = f"{bin_data['BIN']['issuer']['name']}_{bin_data['BIN']['country']['alpha2']}"
                if identity_key not in identities:
                    identity_stix = create_identity(bin_data)
                    identities[identity_key] = identity_stix
                    fs_store.add(identity_stix)
                relationship_stix = create_relationship(card_stix, identities[identity_key])
                fs_store.add(relationship_stix)

def main():
    parser = argparse.ArgumentParser(description='Process credit card data and convert to STIX 2.1 format.')
    parser.add_argument('--input_csv', required=True, help='Input CSV file with credit card data')
    args = parser.parse_args()
    
    logging.info(f"Processing input CSV: {args.input_csv}")
    
    # Ensure the output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    fs_store = FileSystemStore(OUTPUT_DIR)
    process_csv(args.input_csv, fs_store)
    logging.info(f'STIX objects written to {OUTPUT_DIR}')

if __name__ == '__main__':
    main()
