#!/usr/bin/env python
# * coding: utf8 *
'''
mortem.py
A module that sorts out why some geocodes failed
'''

import csv
from glob import glob
from pathlib import Path

import pandas as pd


def process_file(input_data, output_folder, separator):
    index, input_data = input_data

    header = False
    if index == 0:
        header = True

    print(f'processing {input_data}')

    data = pd.read_csv(input_data, encoding='utf-8', sep=separator, index_col=False, quoting=csv.QUOTE_MINIMAL)

    data = data.loc[~(data.message.isnull()), :]
    total = len(data.index)
    output = Path(output_folder)
    output.mkdir(exist_ok=True)

    with open(str(output.joinpath('all-errors.csv')), 'a') as output_file:
        data.to_csv(output_file, header=header, index=False, sep=',', quoting=csv.QUOTE_MINIMAL, escapechar="\\")

    unmatched = data[data['message'].str.contains('No address candidates found with a score of 70 or better.', na=False)]
    with open(str(output.joinpath('not-found.csv')), 'a') as output_file:
        unmatched.to_csv(output_file, header=header, index=False, sep=',', quoting=csv.QUOTE_MINIMAL, escapechar="\\")

    data = data.query('not message == "No address candidates found with a score of 70 or better." and not message.isnull()')
    api_issues = data[~data['message'].str.contains('Expecting value', na=False)]

    with open(str(output.joinpath('api-errors.csv')), 'a') as output_file:
        api_issues.to_csv(output_file, header=header, index=False, sep=',', quoting=csv.QUOTE_MINIMAL, escapechar="\\")

    incomplete = data[data['message'].str.contains('Expecting value', na=False)]

    with open(str(output.joinpath('incomplete-errors.csv')), 'a') as output_file:
        incomplete.to_csv(output_file, header=header, index=False, sep=',', quoting=csv.QUOTE_MINIMAL, escapechar="\\")

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
    pattern = str(Path(input_data).joinpath('*.csv'))

    print(f'finding files in {input_data} with {pattern}')
    files = glob(pattern)

    results = [process_file(item, output_folder, separator) for item in enumerate(files)]

    print(f'\ntotal unmatched records: {_sum_key(results, "total")}')
    print('unmatched address breakdown')
    print(f'  incomplete addresses (missing street or zone): {_sum_key(results, "incomplete")}')
    print(f'  api errors: {_sum_key(results, "api_errors")}')
    print(f'  address not found (bad address or formatting): {_sum_key(results, "unmatchable")}')
