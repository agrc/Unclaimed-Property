#!/usr/bin/env python
# * coding: utf8 *
'''
cloud-geocode

Usage:
    cloud-geocode create partitions --input-csv=input-csv [--output-partitions=output-partitions --chunk-size=size --separator=sep --column-names=names...]
    cloud-geocode create jobs [--input-jobs=input-jobs --output-jobs=output-jobs]
    cloud-geocode upload [--bucket=bucket --input-folder=upload-folder]
    cloud-geocode post-mortem [--result-folder=input-folder --separator=sep --output-folder=output-folder]

Arguments:
--input-jobs=input-jobs                 The parent folder path to the partitioned csv files [default: ./../data/partitioned]
--output-jobs=output-jobs               The parent folder path for the job.yml files to be placed [default: ./../jobs/]
--input-csv=input-csv                   The large csv file to partition into smaller files
--output-partitions=output-partitions   The parent folder path to place the csv partitions [default: ./../data/partitioned]
--chunk-size=size                       The amount of records to have in each partition [default: 150000]
--separator=sep                         The csv file field separator [default: ,]
--column-names=names                    An array of the column names in the csv
--input-folder=upload-folder            The parent folder path containting the csv files to upload to a bucket [default: ../data/partitioned]
--bucket=bucket                         The google cloud bucket to upload the files to [default: geocoder-csv-storage-95728]
--result-folder=input-folder             The input folder containing csv files [default: ./../data/results]
--output-folder=output-folder           The place to store the post mortem issue csv's [default: ./../data/postmortem/]
'''

import sys
from pathlib import Path

from docopt import docopt

from .jobs import create_jobs
from .mortem import mortem
from .partition import create_partitions
from .upload import upload_files


def main():
    '''the main method to be called when the script is invoked
    '''
    args = docopt(__doc__, version='cloud geocoding cli v1.0.0')

    if args['create'] and args['partitions']:
        create_partitions(args['--input-csv'], args['--output-partitions'], int(args['--chunk-size']), args['--separator'], args['--column-names'])

        return

    if args['create'] and args['jobs']:
        create_jobs(args['--input-jobs'], args['--output-jobs'])

        return

    if args['upload']:
        uploads = sorted(Path(args['--input-folder']).glob('*.csv'))

        for path in uploads:
            upload_files(str(path), args['--bucket'])

        return

    if args['post-mortem']:
        mortem(args['--result-folder'], args['--output-folder'], args['--separator'])

        return


if __name__ == '__main__':
    sys.exit(main())
