#!/usr/bin/env python
# * coding: utf8 *
"""
Cloud Geocoding

Usage:
  geocode.py geocode <input_csv>
    (--from-bucket=bucket --output-bucket=output)
    [--api-key=key --street-field=street --zone-field=zone --id-field=id --testing=test, --ignore-failure=failures]

Options:
  <input_csv>                    The name of the csv inside the --from-bucket
  --from-bucket=bucket           The bucket to find the <input_csv>
  --output-bucket=output         The bucket to save the results to
  --street-field=field           The field name containing the street address [default: address]
  --zone-field=zone              The field containing the zip code or city name [default: zone]
  --id-field=id                  The field containing a unique id to zip the results back together [default: id]
  --testing=test                 Trick the tool to not use google data and from and to become file paths [default: false]
  --ignore-failure=failures      Ignore the failure threshold. Useful when trying to geocode garbage data [default: false]
"""
import csv
import logging
import random
import re
import sys
import time
import uuid
from pathlib import Path
from string import Template
from time import perf_counter

import google.cloud.logging
import requests
from docopt import docopt
from google.cloud import storage

CLIENT = google.cloud.logging.Client()
CLIENT.setup_logging()

SPACES = re.compile(r'(\s\d/\d\s)|/|(\s#.*)|%|(\.\s)|\?')
RATE_LIMIT_SECONDS = (0.015, 0.03)
HOST = 'webapi-api'
HEADER = ('primary_key', 'input_address', 'input_zone', 'score', 'x', 'y', 'message')


def make_unique(name):
    return f'{uuid.uuid4().hex}-{name}'


def bring_job_data_local(bucket_name, source_blob_name, destination_file_name, testing):
    """Downloads a blob from the bucket
    """
    if testing.lower() == 'true':
        return str(Path(bucket_name).joinpath(source_blob_name))

    logging.info('creating storage client')

    storage_client = storage.Client()

    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(source_blob_name)

    logging.info('downloading %s to %s', source_blob_name, destination_file_name)

    blob.download_to_filename(destination_file_name)

    logging.info('Downloading %s complete', source_blob_name)

    return destination_file_name


def store_job_results(bucket_name, source_file_name, destination_blob_name, testing):
    """Uploads a file to the bucket
    """
    if testing.lower() == 'true':
        return source_file_name

    storage_client = storage.Client()
    item = make_unique(destination_blob_name)

    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(item)

    blob.upload_from_filename(source_file_name)

    logging.info('Upload %s complete', item)


def is_key_valid(key):
    if key:
        return True

    return False


def cleanse_address(data):
    """cleans up address garbage
    """
    replacement = ' '
    street = str(data).strip()

    street = SPACES.sub(replacement, street)

    for char in range(0, 31):
        street = street.replace(chr(char), replacement)
    for char in range(33, 37):
        street = street.replace(chr(char), replacement)

    street = street.replace(chr(38), 'and')

    for char in range(39, 47):
        street = street.replace(chr(char), replacement)
    for char in range(58, 64):
        street = street.replace(chr(char), replacement)
    for char in range(91, 96):
        street = street.replace(chr(char), replacement)
    for char in range(123, 255):
        street = street.replace(chr(char), replacement)

    return street.strip()


def cleanse_zone(data):
    """cleans up zone garbage
    """
    zone = SPACES.sub(' ', str(data)).strip()

    if len(zone) > 0 and zone[0] == '8':
        zone = zone.strip()[:5]

    return zone


def format_time(seconds):
    """seconds: number
    returns a human-friendly string describing the amount of time
    """
    minute = 60.00
    hour = 60.00 * minute

    if seconds < 30:
        return '{} ms'.format(int(seconds * 1000))

    if seconds < 90:
        return '{} seconds'.format(round(seconds, 2))

    if seconds < 90 * minute:
        return '{} minutes'.format(round(seconds / minute, 2))

    return '{} hours'.format(round(seconds / hour, 2))


def execute_job(data, options):
    """loop over the csv data and geocode the rows
    """
    url_template = Template(f'http://{HOST}/api/v1/geocode/$street/$zone')
    sequential_fails = 0
    success = 0
    fail = 0
    score = 0
    total = 0

    logging.info('executing job on %s with %s', data, options)

    with open(data, newline='') as csv_file, open('result.csv', 'w') as result_file:
        reader = csv.DictReader(csv_file, delimiter='|', quoting=csv.QUOTE_NONE)
        writer = csv.writer(result_file)

        writer.writerow(HEADER)

        start = perf_counter()
        for row in reader:
            if options['--testing'].lower() == 'true' and total > 50:
                return 'result.csv'

            if options['--ignore-failure'].lower() != 'true' and sequential_fails > 25:
                logging.warning('passed continuous fail threshold. failing entire job.')

                return None

            street = cleanse_address(row[options['--street-field']])
            zone = cleanse_zone(row[options['--zone-field']])

            url = url_template.substitute({'street': street, 'zone': zone})

            primary_key = row[options['--id-field']]

            time.sleep(random.uniform(RATE_LIMIT_SECONDS[0], RATE_LIMIT_SECONDS[1]))

            try:
                request = requests.get(url, timeout=5, params={
                    'apiKey': options['--api-key']
                })

                response = request.json()

                if request.status_code != 200:
                    fail += 1
                    total += 1
                    sequential_fails += 1

                    writer.writerow((primary_key, street, zone, 0, 0, 0, response['message']))

                    continue

                match = response['result']
                match_score = match['score']
                location = match['location']
                match_x = location['x']
                match_y = location['y']

                sequential_fails = 0
                success += 1
                total += 1
                score += match_score

                writer.writerow((primary_key, street, zone, match_score, match_x, match_y, None))
            except Exception as ex:
                fail += 1
                total += 1

                writer.writerow((primary_key, street, zone, 0, 0, 0, str(ex)[:500]))

            if total % 10000 == 0:
                logging.info('Total requests: %s failure rate: %.2f%% average score: %d time taken: %s', total, (100 * fail / total), score / success, format_time(perf_counter() - start))
                start = perf_counter()

        logging.info('Job Completed')
        logging.info('Total requests: %s failure rate: %.2f%% average score: %d time taken: %s', total, (100 * fail / total), score / success, format_time(perf_counter() - start))

    return 'result.csv'


def main():
    """the main method to be called when the script is invoked
    """
    args = docopt(__doc__, version='cloud geocoding job v1.0.0')
    logging.info('starting job')

    if not is_key_valid(args['--api-key']):
        logging.info("Api key check failed")

    job_data = bring_job_data_local(args['--from-bucket'], args['<input_csv>'], 'job.csv', args['--testing'])

    result = execute_job(job_data, args)

    store_job_results(args['--output-bucket'], result, args['<input_csv>'], args['--testing'])


if __name__ == '__main__':
    main()
