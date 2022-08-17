#!/usr/bin/env python
# * coding: utf8 *
"""
mortem.py
A module that sorts out why some geocodes failed
"""

import csv
from pathlib import Path

import pandas as pd

from sweeper.address_parser import Address


def process_file(input_data, output_folder, separator):
    """This takes csvs in an input_data folder and groups them by error types.

    - `total`: all of the unmatched addresses from the geocoded results
    - `api_errors`: a subset of total where the message is not a normal api response
    - `incomplete`: typically errors that have null parts.
       This should be inspected because other errors can get mixed in here
    - `unmatchable`: all the addresses that 404'd as not found by the api
    """
    index, input_data = input_data

    header = False
    if index == 0:
        header = True

    print(f'processing {input_data}')

    data = pd.DataFrame(
        pd.read_csv(input_data, encoding='utf-8', sep=separator, index_col=False, quoting=csv.QUOTE_MINIMAL)
    )

    data = data.loc[~(data.message.isnull()), :]
    total = len(data.index)
    output = Path(output_folder)
    output.mkdir(exist_ok=True)

    data.to_csv(
        output / 'all_errors.csv',
        mode='a',
        encoding='utf-8',
        header=header,
        index=False,
        sep=',',
        quoting=csv.QUOTE_MINIMAL,
        escapechar="\\"
    )

    unmatched = data[
        data['message'].str.contains('No address candidates found with a score of 70 or better.', na=False)]

    unmatched.to_csv(
        output / 'not_found.csv',
        mode='a',
        encoding='utf-8',
        header=header,
        index=False,
        sep=',',
        quoting=csv.QUOTE_MINIMAL,
        escapechar="\\"
    )

    data = data.query(
        'not message == "No address candidates found with a score of 70 or better." and not message.isnull()',
        engine='python'
    )
    api_issues = data[~data['message'].str.contains('Expecting value', na=False)]

    api_issues.to_csv(
        output / 'api_errors.csv',
        mode='a',
        encoding='utf-8',
        header=header,
        index=False,
        sep=',',
        quoting=csv.QUOTE_MINIMAL,
        escapechar="\\"
    )

    incomplete = data[data['message'].str.contains('Expecting value', na=False)]

    incomplete.to_csv(
        output / 'incomplete_errors.csv',
        mode='a',
        encoding='utf-8',
        header=header,
        index=False,
        sep=',',
        quoting=csv.QUOTE_MINIMAL,
        escapechar="\\"
    )

    return {
        'total': total,
        'unmatchable': len(unmatched.index),
        'api_errors': len(api_issues.index),
        'incomplete': len(incomplete.index),
    }


def _sum_key(dictionary, key):
    result = 0

    for item in dictionary:
        result += item[key]

    return result


def mortem(input_data, output_folder, separator):
    """This takes csvs in an input_data folder and groups them by error types writing the results to csv.

    - `all_errors.csv`: all of the unmatched addresses from the geocoded results
    - `api_errors.csv`: a subset of `all_errors.csv` where the message is not a normal api response
    - `all_errors_job.csv`: all of the unmatched addresses from the geocoded results but in a format that can be processed by the cluster.
    - `incomplete_errors.csv`: typically errors that have null parts. This should be inspected because other errors can get mixed in here
    - `not_found.csv`: all the addresses that 404'd as not found by the api. `post-mortem normalize` will run these addresses through sweeper
    """
    files = sorted(Path(input_data).glob('*.csv'))

    print('removing any old post mortem files')
    _ = [item.unlink() for item in Path(output_folder).glob('*.csv')]

    results = [process_file(item, output_folder, separator) for item in enumerate(files)]

    fix_me = list(Path(output_folder).glob('all_errors.csv'))[0]
    all_errors = pd.DataFrame(
        pd.read_csv(fix_me, encoding='utf-8', sep=separator, index_col=False, quoting=csv.QUOTE_MINIMAL)
    )
    all_errors.rename(columns={'primary_key': 'id', 'input_address': 'address', 'input_zone': 'zone'}, inplace=True)

    all_errors.drop(['score', 'x', 'y', 'message'], axis=1, inplace=True)

    all_errors.to_csv(
        Path(output_folder) / 'all_errors_job.csv',
        mode='a',
        encoding='utf-8',
        header=True,
        index=False,
        sep='|',
        quoting=csv.QUOTE_MINIMAL,
        escapechar="\\"
    )

    print(f'\ntotal unmatched records: {_sum_key(results, "total")}')
    print('unmatched address breakdown')
    print(f'  incomplete addresses (missing street or zone): {_sum_key(results, "incomplete")}')
    print(f'  api errors: {_sum_key(results, "api_errors")}')
    print(f'  address not found (bad address or formatting): {_sum_key(results, "unmatchable")}')


def rebase(input_data, specific_file, separator, message):
    """This method updates the csv files in the input_data folder with any new geocodes
    found in the specific_file. It also updates the message from the old error to a new
    value so it can be differentiated from the others."""
    files = list(Path(input_data).glob('*.csv'))
    all_errors = [item for item in files if item.match(specific_file)][0]
    files.remove(all_errors)

    new_data = pd.DataFrame(
        pd.read_csv(
            all_errors, index_col='primary_key', dtype=str, encoding='utf-8', sep=separator, quoting=csv.QUOTE_MINIMAL
        )
    )

    new_data = new_data.loc[~(new_data.score == "0")]  #: remove 0 score records

    print(f'found {len(new_data.index)} records to rebase')

    new_data.message = message

    for result in files:
        data = pd.DataFrame(
            pd.read_csv(
                result, index_col='primary_key', dtype=str, encoding='utf-8', sep=separator, quoting=csv.QUOTE_MINIMAL
            )
        )
        data.update(new_data)
        data.to_csv(result, encoding='utf-8', sep=separator, quoting=csv.QUOTE_MINIMAL)


def try_standardize_unmatched(input_csv, output_file):
    """This method takes an input, parses it with sweeper and
    tries to standardize the address for another geocode run"""
    total = 0
    invalid = 0

    def normalize(street):
        try:
            address = Address(street)

            if address.po_box:
                return None

            parts = [
                address.address_number, address.address_number_suffix, address.prefix_direction, address.street_name,
                address.street_type, address.street_direction
            ]

            normalized = ' '.join([part for part in parts if part is not None])

            if normalized == street:
                return None

            return normalized
        except Exception:
            return None

    print('reading unmatched records')
    data = pd.DataFrame(pd.read_csv(input_csv, encoding='utf-8', index_col=False, quoting=csv.QUOTE_MINIMAL))
    total = len(data.index)

    print('normalizing address data')
    data['input_address'] = data['input_address'].str.replace(' +', ' ', regex=False)
    data['address'] = data.apply(lambda row: normalize(row['input_address']), axis=1)

    invalid = data['primary_key'].count()
    data.dropna(inplace=True)
    invalid = invalid - data['primary_key'].count()

    not_found_path = Path(input_csv)
    api_errors = not_found_path.with_name('api_errors.csv')
    extra = pd.DataFrame()

    if api_errors.exists():
        extra = pd.DataFrame(pd.read_csv(str(api_errors), encoding='utf-8', index_col=False, quoting=csv.QUOTE_MINIMAL))
        extra.rename(columns={'input_address': 'address'}, inplace=True)

        print('found api errors... appending')
        data = pd.concat([data, extra])
        total += len(extra.index)

    data.drop(['score', 'x', 'y', 'message', 'input_address'], axis=1, inplace=True)

    data.rename(columns={'primary_key': 'id', 'input_zone': 'zone'}, inplace=True)
    data = data[['id', 'address', 'zone']]

    print('writing normalized addresses')
    data.to_csv(output_file, index=False, sep='|', header=True, quoting=csv.QUOTE_MINIMAL, escapechar="\\")

    print(f'\nread {total + len(extra.index)} rows')
    print(f'invalid addresses {(100 * invalid / total):%.2f%}%')
    print(f'{invalid} addresses could not be parsed')
    print(f'saving {data["id"].count()} items for retry')
