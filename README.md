# creditcard2stix

## Overview

![](docs/creditcard2stix.png)

This script contains logic to enrich a credit card number input with more information about the card (e.g. issuer, country, etc.).

The script takes a card number (required), card holder name (optional), expiry date (optional), security code (optional) as inputs (as a list) and outputs a range of STIX 2.1 objects for each credit card with added enrichment data.

You can also optionally create a STIX Report object to document details about where this card data was obtained.

This repository also contains a demo script so that you can try the script with some dummy credit card data to see how it works.

## tl;dr

[![creditcard2stix](https://img.youtube.com/vi/mPSQ5FRW0hM/0.jpg)](https://www.youtube.com/watch?v=mPSQ5FRW0hM)

[Watch the demo](https://www.youtube.com/watch?v=mPSQ5FRW0hM).

## Install 

```shell
# clone the latest code
git clone https://github.com/muchdogesec/creditcard2stix
cd creditcard2stix
# create a venv
python3 -m venv creditcard2stix-venv
source creditcard2stix-venv/bin/activate
# install requirements
pip3 install -r requirements.txt
```

Then you need to add your BIN List API key ([get one for free here](https://bincheck.io/api));

```shell
cp .env.example .env
```

And add your

```txt
BIN_LIST_API_KEY=
```

## Run

```shell
python3 creditcard2stix.py --input_csv FILE.csv --report_csv REPORT.csv
```

Where:

* `--input_csv` (required): is the file containing card numbers and should be of type `.csv` and contain the headers:
    * `card_number` (required)
    * `card_security_code` (optional)
    * `card_valid_date` (optional)
    * `card_expiry_date` (optional)
    * `card_holder_name` (optional)
* `--report_csv` (optional): a file containing details about the dump. If passed the CSV should contain the headers, and only two rows should exist (header row and report detail row)
    * `name` (required)
    * `description` (optional)
    * `published` (optional) in format YYYY-MM-DD, else time of script execution will be used

### Examples

The most common way to use creditcard2stix is to pass the list of leaked cards with a report detailing the dump like so;

```shell
python3 creditcard2stix.py \
    --input_csv demos/dummy_credit_cards_10.csv \
    --report_csv demos/my_fake_report.csv
```

(see `demos/credit-card-bundle-all-props-with-report.json`)

And without optional fields and no report generated;

```shell
python3 creditcard2stix.py \
    --input_csv demos/dummy_credit_cards_without_optional_fields.csv
```

(see `demos/credit-card-bundle-basic-props-no-report.json`)

Note, if the same `card_number` is found in the file more than once, the record with the most properties will be used for conversion.

## Data Sources

BIN Check have an API that allows you to pass parts of a bank card to get more data about it (e.g. bank issuer, bank location, etc.).

[You get an API key here](https://rapidapi.com/trade-expanding-llc-trade-expanding-llc-default/api/bin-ip-checker).

Their API accepts requests as follows;

```shell
curl --request POST \
    --url 'https://bin-ip-checker.p.rapidapi.com/?bin=5<CARD_NUMBER>' \
    --header 'Content-Type: application/json' \
    --header 'x-rapidapi-host: bin-ip-checker.p.rapidapi.com' \
    --header 'x-rapidapi-key: <API_KEY>' \
    --data '{"bin":"<CARD_NUMBER>"}'
```

e.g. for `5319031972219450327`;

```json
{
  "success": true,
  "code": 200,
  "BIN": {
    "valid": true,
    "number": 531903,
    "length": 6,
    "scheme": "MASTERCARD",
    "brand": "MASTERCARD",
    "type": "DEBIT",
    "level": "STANDARD",
    "currency": "USD",
    "issuer": {
      "name": "JACK HENRY & ASSOCIATES",
      "website": "http://www.jackhenry.com",
      "phone": "+14172356652"
    },
    "country": {
      "name": "UNITED STATES",
      "native": "United States",
      "flag": "🇺🇸",
      "numeric": "840",
      "capital": "Washington, D.C.",
      "currency": "USD",
      "currency_symbol": "$",
      "region": "Americas",
      "subregion": "Northern America",
      "idd": "1",
      "alpha2": "US",
      "alpha3": "USA",
      "language": "English",
      "language_code": "EN",
      "latitude": 34.05223,
      "longitude": -118.24368
    }
  }
}
```

This data can then be mapped to STIX 2.1 objects.

## Mapping

Here's an example of how the STIX objects are structured in the output;

https://miro.com/app/board/uXjVKnlbRaY=/

Note, `credit-card-transaction`, `threat-actor`, and `location` of the holder Object are not handled by this code. They are only included to illustrate how this data could be embedded into a wider intelligence graph.

#### Automatically imported objects

These objects are imported from the URLs and generated by the STIX2 library into the filestore. This is done as they are included in the final bundle file generated by creditcard2stix.

* Bank Card Extension Definition: https://raw.githubusercontent.com/muchdogesec/stix2extensions/main/extension-definitions/scos/bank-card.json
* creditcard2stix Identity: https://raw.githubusercontent.com/muchdogesec/stix4doge/main/objects/identity/creditcard2stix.json
* creditcard2stix Marking Definition: https://raw.githubusercontent.com/muchdogesec/stix4doge/main/objects/marking-definition/creditcard2stix.json

#### Credit Card number

Each credit card number in the input `.csv` file is compared to the BIN list API.

If a credit card number returns data from BIN list (where `valid=true`) then an STIX2 object is generated and stored in the filesytem (in the `stix2_objects` directory) with the following structure;

```json
{
    "type": "bank-card",
    "spec_version": "2.1",
    "id": "<bank-card--UUID V5>",
    "format": "<lookup->BIN.type>",
    "number": "<csv->card_number>",
    "scheme": "<lookup->BIN.scheme>",
    "brand": "<lookup->BIN.brand>",
    "currency": "<lookup->BIN.currency>",
    "issuer_ref": "<stix id of the identity object generated for linked bank>",
    "holder_ref": "<stix id of the identity object generated for the holder, if csv.card_holder_name exists>",
    "valid_from": "<csv->card_valid_date, if exists>",
    "valid_to": "<csv->card_expiry_date, if exists>",
    "security_code": "<csv->card_security_code, if exists>",
    "extensions": {
        "extension-definition--7922f91a-ee77-58a5-8217-321ce6a2d6e0": {
            "extension_type": "new-sco"
        }
    }
}
```

The UUID is generated using the namespace `00abedb4-aa42-466c-9c01-fed23315a9b7` (OASIS STIX namespace) and the `number` value.

If a credit card pattern does not match that of an entry from BIN list (response is not 200 or where `valid=false`) a STIX object is generated, but without any of the lookup fields present.

#### Bank Identity

For every unique bank_name and BIN.issuer.name and BIN.country.alpha2 a STIX 2.1 Identity object is generated as follows:

```json
{
  "type": "identity",
  "spec_version": "2.1",
  "id": "identity--<UUID V5>",
  "created_by_ref": "identity--d287a5a4-facc-5254-9563-9e92e3e729ac",
  "created": "2020-01-01T00:00:00.000Z",
  "modified": "2020-01-01T00:00:00.000Z",
  "name": "<BIN.issuer.name> (<BIN.country.alpha2>)",
  "identity_class": "organization",
  "sectors": [
  	"financial-services"
  ],
  "contact_information": "* Bank URL: <BIN.issuer.website>,\n* Bank Phone: <BIN.issuer.phone>",
  "object_marking_refs": [
  	"marking-definition--94868c89-83c2-464b-929b-a1a8aa3c8487"
  	"marking-definition--d287a5a4-facc-5254-9563-9e92e3e729ac"
   ]
}
```

The UUID is generated using the namespace `d287a5a4-facc-5254-9563-9e92e3e729ac` and the `name` value.

Note, if more than one credit card in the list has the same issuer (by name and country), only one Identity is created for it.

#### Holder Identity

If the input csv contains a card_holder_name value, an Identity object will be created for it as follows:

```json
{
  "type": "identity",
  "spec_version": "2.1",
  "id": "identity--<UUIDv5>",
  "created_by_ref": "identity--d287a5a4-facc-5254-9563-9e92e3e729ac",
  "created": "2020-01-01T00:00:00.000Z",
  "modified": "2020-01-01T00:00:00.000Z",
  "name": "<csv.card_holder_name>",
  "identity_class": "individual",
  "object_marking_refs": [
    "marking-definition--94868c89-83c2-464b-929b-a1a8aa3c8487"
    "marking-definition--d287a5a4-facc-5254-9563-9e92e3e729ac"
   ]
}
```

The UUID is generated using the namespace `d287a5a4-facc-5254-9563-9e92e3e729ac` and the `name+<card_number_associated_with_name>` value (e.g. `Mr Dogesec+5319031972219450327`).

#### Report

If user enters a reports csv file when running the command, a report objects will be generated as follows;

```json
{
    "type": "report",
    "spec_version": "2.1",
    "id": "report--<UUID V5>",
    "created_by_ref": "identity--d287a5a4-facc-5254-9563-9e92e3e729ac",
    "created": "<published if entered, else script runtime>",
    "modified": "<published, else script runtime>",
    "name": "<name>",
    "description": "<description if entered, else omitted>",
    "published": "<published if entered, else script runtime>",
    "report_types": [
        "observed-data"
    ],
    "object_refs": [
        "<ALL STIX CREDIT CARDS IDS GENERATED ON THIS IMPORT>",
    ]
}
```

The UUID v5 is generated using the namespace `d287a5a4-facc-5254-9563-9e92e3e729ac` and an md5 hash of the credit card CSV file inputted.

### Bundle

This script outputs all the objects into a single STIX 2.1 bundle `ransomwhere-bundle.json`

```json
{
    "type": "bundle",
    "id": "bundle--<UUIDV5>",
    "objects": [
        "ALL STIX OBJECTS CREATED"
    ]
}
```

Note the bundle generated includes all Identity objects for credit cards that are referenced inside Relationship objects.

The UUID is generated using the namespace `d287a5a4-facc-5254-9563-9e92e3e729ac` and the md5 hash of all objects sorted in the bundle.

## Useful utilitles

### `utilities/generate_credit_cards.py`

Running

```shell
python3 utilities/generate_credit_cards.py --n "<optional: Number of credit card numbers to generate>" --t "<optional: card scheme to generate>"
```

Will generate a list of fake credit card numbers that follow the issuers schema.

e.g.

```shell
python3 utilities/generate_credit_cards.py
```

```shell
python3 utilities/generate_credit_cards.py --n 1000 --t amex mastercard
```

### `tests/*`

Contains a range of CSVs that cover various ways the script can be used. Useful for understanding the logic of this script.

```shell
python3 creditcard2stix.py --input_csv tests/same_card_appears_twice.csv
```

## Useful supporting tools

* The `bin_ranges.csv` used by creditcard2stix `generate_credit_cards.py` comes from [this repository](https://github.com/binlist/data)
* To generate STIX 2.1 Objects: [stix2 Python Lib](https://stix2.readthedocs.io/en/latest/)
* The STIX 2.1 specification: [STIX 2.1 docs](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html)

## Support

[Minimal support provided via the DOGESEC community](https://community.dogesec.com/).

## License

[Apache 2.0](/LICENSE).