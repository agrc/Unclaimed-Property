#!/usr/bin/env python
# * coding: utf8 *
"""
cloud-geocode

Usage:
    cli create partitions --input-csv=input-csv [--output-partitions=output-partitions --chunk-size=size --separator=sep --column-names=names...]
    cli create jobs [--input-jobs=input-jobs --output-jobs=output-jobs --single=specific-file]
    cli upload [--bucket=bucket --input-folder=upload-folder --single=specific-file]
    cli create enhancement-gdb [--output-gdb-folder=output-gdb]
    cli enhance [--csv-folder=geocoded-results]
    cli merge [--final-folder=final-folder]
    cli rename [--csv-folder=geocoded-results]
    cli post-mortem [--result-folder=input-folder --separator=sep --output-folder=output-folder]
    cli post-mortem rebase [--result-folder=input-folder --single=specific-file --separator=sep --message=message]
    cli post-mortem normalize [--unmatched=input-csv --output-normalized=file-path]

Arguments:
--input-jobs=input-jobs                 The parent folder path to the partitioned csv files [default: ./../data/partitioned]
--output-jobs=output-jobs               The parent folder path for the job.yml files to be placed [default: ./../jobs/]
--single=specific-file                  The name of a single file to be processed
--input-csv=input-csv                   The large csv file to partition into smaller files
--output-partitions=output-partitions   The parent folder path to place the csv partitions [default: ./../data/partitioned]
--chunk-size=size                       The amount of records to have in each partition [default: 150000]
--separator=sep                         The csv file field separator [default: ,]
--column-names=names                    An array of the column names in the csv
--input-folder=upload-folder            The parent folder path containing the csv files to upload to a bucket [default: ../data/partitioned]
--bucket=bucket                         The google cloud bucket to upload the files to [default: ut-dts-agrc-geocoding-dev-source]
--result-folder=input-folder            The input folder containing csv files [default: ./../data/geocoded-results]
--output-folder=output-folder           The place to store the post mortem issue csv's [default: ./../data/postmortem/]
--unmatched=input-csv                   The path to the not_found.csv file generated from post-mortem or other input [default: ./../data/postmortem/not_found.csv]
--output-normalized=file-path           The place to store the normalized addresses [default: ./../data/postmortem/normalized.csv]
--output-gdb-folder=output-gdb          The parent directory of the file geodatabase containing the enhancement layers [default: ./../data/enhanced]
--csv-folder=geocoded-results           The parent directory of the geocoded files to enhanced [default: ./../data/geocoded-results]
--final-folder=final-folder             The parent directory of the enhanced csv files [default: ./../data/results]
--message=message                       The message to be used in the rebase command [default: post mortem replaced]
"""

import sys
from pathlib import Path

from docopt import docopt
from num2words import num2words

from .jobs import create_jobs
from .mortem import mortem, rebase, try_standardize_unmatched
from .partition import create_partitions
from .upload import upload_files
from .enhance import create_enhancement_gdb, enhance, merge


def main():
    """the main method to be called when the script is invoked
    """
    args = docopt(__doc__, version='cloud geocoding cli v1.0.0')

    if args['create'] and args['partitions']:
        create_partitions(
            args['--input-csv'], args['--output-partitions'], int(args['--chunk-size']), args['--separator'],
            args['--column-names']
        )

        return

    if args['create'] and args['jobs']:
        create_jobs(args['--input-jobs'], args['--output-jobs'], args['--single'])

        return

    if args['create'] and args['enhancement-gdb']:
        create_enhancement_gdb(args['--output-gdb-folder'])

        return

    if args['upload']:
        uploads = sorted(Path(args['--input-folder']).glob('*.csv'))
        print(f'found {len(uploads)} files in {args["--input-folder"]}')

        if args['--single']:
            print(f'searching for {args["--single"]}')
            uploads = [item for item in uploads if item.name.casefold() == args['--single'].casefold()]

        print(f'uploading {len(uploads)} files')
        for path in uploads:
            upload_files(str(path), args['--bucket'])

        return

    if args['rename']:
        rename_files = Path(args['--csv-folder']).glob('*.csv')

        for path in rename_files:
            partition = path.stem.split("_")[1]
            new_name = f'{partition}.csv'
            print(f'renaming {path.stem} to {new_name}')

            path.rename(path.parent / new_name)

        return

    if args['enhance']:
        enhance(args['--csv-folder'])

        return

    if args['merge']:
        merge(args['--final-folder'])

    if args['post-mortem'] and args['rebase']:
        rebase(args['--result-folder'], args['--single'], args['--separator'], args['--message'])
        return

    if args['post-mortem'] and args['normalize']:
        try_standardize_unmatched(args['--unmatched'], args['--output-normalized'])

        return

    if args['post-mortem']:
        mortem(args['--result-folder'], args['--output-folder'], args['--separator'])

        return


if __name__ == '__main__':
    sys.exit(main())
