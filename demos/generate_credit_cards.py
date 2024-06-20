import random
import pandas as pd
from datetime import datetime
import argparse
import os

# Load the CSV file
file_path = 'bin_ranges.csv'
df = pd.read_csv(file_path)

# Default logic for card number length
default_lengths = {
    'visa': [16, 19],
    'mastercard': [16, 19],
    'discover': [14, 16],
    'unionpay': [16, 17, 18, 19]
}

# card_security_code lengths by card type
card_security_code_lengths = {
    'visa': 3,
    'mastercard': 3,
    'discover': 3,
    'unionpay': 3,
    'amex': 4,
    'diners': 3
}

# Expiry date range
expiry_start = datetime.strptime('01/28', '%m/%y')
expiry_end = datetime.strptime('12/28', '%m/%y')

# Valid date range
valid_start = datetime.strptime('01/23', '%m/%y')
valid_end = datetime.strptime('12/23', '%m/%y')

# Sample first and last names for generating cardholder names
first_names = ['John', 'Jane', 'Alex', 'Chris', 'Pat', 'Sam', 'Taylor', 'Morgan', 'Jamie', 'Jordan']
last_names = ['Smith', 'Johnson', 'Williams', 'Jones', 'Brown', 'Davis', 'Miller', 'Wilson', 'Moore', 'Taylor']

def generate_random_card_holder_name():
    first_name = random.choice(first_names)
    last_name = random.choice(last_names)
    return f"{first_name} {last_name}"

def generate_random_credit_card(card_type, iin_start, iin_end, number_length=None):
    try:
        if number_length is None or pd.isna(number_length):
            number_length = random.choice(default_lengths.get(card_type, [16]))
        else:
            number_length = int(number_length)

        iin_start_str = str(int(iin_start))
        iin_end_str = str(int(iin_end)) if not pd.isna(iin_end) else ''

        middle_length = number_length - len(iin_start_str) - len(iin_end_str)
        card_number = iin_start_str + ''.join([str(random.randint(0, 9)) for _ in range(middle_length)]) + iin_end_str

        card_security_code_length = card_security_code_lengths.get(card_type, 3)
        card_security_code = ''.join([str(random.randint(0, 9)) for _ in range(card_security_code_length)])

        card_expiry_date = (expiry_start + (expiry_end - expiry_start) * random.random()).strftime('%m/%y')
        card_valid_date = (valid_start + (valid_end - valid_start) * random.random()).strftime('%m/%y')

        card_holder_name = generate_random_card_holder_name()

        return card_number, card_security_code, card_expiry_date, card_valid_date, card_holder_name
    except Exception as e:
        print(f"Error generating card for {card_type}: {e}")
        return None, None, None, None, None

def generate_credit_cards(num_cards, card_types):
    cards = []
    for _ in range(num_cards):
        try:
            row = df[df['scheme'].isin(card_types)].sample(1).iloc[0]
            card_type = row['scheme']
            iin_start = row['iin_start']
            iin_end = row['iin_end']
            number_length = row['number_length']

            card_number, card_security_code, card_expiry_date, card_valid_date, card_holder_name = generate_random_credit_card(card_type, iin_start, iin_end, number_length)
            if card_number and card_security_code and card_expiry_date and card_valid_date and card_holder_name:
                cards.append({
                    'card_number': card_number,
                    'card_security_code': card_security_code,
                    'card_valid_date': card_valid_date,
                    'card_expiry_date': card_expiry_date,
                    'card_holder_name': card_holder_name
                })
        except Exception as e:
            print(f"Error processing row: {e}")
    return cards

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate random credit card numbers.")
    parser.add_argument('-n', '--number', type=int, default=20000, help="Number of credit card numbers to generate.")
    parser.add_argument('-t', '--types', nargs='+', default=['visa', 'mastercard', 'discover', 'unionpay', 'amex', 'diners'], help="Types of cards to generate (e.g. visa mastercard).")

    args = parser.parse_args()

    num_cards = args.number
    card_types = args.types

    cards = generate_credit_cards(num_cards, card_types)

    # Save the output to the demos directory
    output_file = os.path.join('dummy_credit_cards.csv')
    df_output = pd.DataFrame(cards)
    df_output.to_csv(output_file, index=False)

    print(f"Generated {num_cards} credit card numbers and saved to {output_file}.")
