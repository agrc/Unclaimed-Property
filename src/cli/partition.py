#!/usr/bin/env python
# * coding: utf8 *
"""
partition.py
A module that splits a large csv into smaller ones
"""

import csv
from pathlib import Path
from shutil import rmtree

import pandas as pd


def create_partitions(input_data, output_data, chunk_size, separator, column_names):
    """partitions a single file into multiple based on chunks
    """
    for i, partition in enumerate(
        pd.read_csv(
            input_data,
            encoding='utf-8',
            dtype={'category': 'string', 'partial-id': 'Int64', 'address': 'string', 'zone': 'string'},
            sep=separator,
            header=None,
            names=column_names,
            index_col=False,
            chunksize=chunk_size,
            quoting=csv.QUOTE_NONE
        )
    ):
        print(f'writing partition {i}')

        partitioned_csv = Path(output_data)

        if partitioned_csv.exists() and i == 0:
            rmtree(partitioned_csv)

        partitioned_csv.mkdir(parents=True, exist_ok=True)

        partitioned_csv = partitioned_csv.joinpath(f'partition_{i}.csv')
        partitioned_csv.touch(exist_ok=False)

        partition = partition.assign(id=partition.category + partition['partial-id'].map(str))
        columns = ['id', 'address', 'zone']
        partition = partition.reindex(columns, axis=1)

        for col in columns:
            try:
                partition[col] = partition[col].str.replace('"', '')
            except AttributeError:
                pass

        with open(partitioned_csv, 'w', encoding='utf-8') as output_file:
            partition.to_csv(output_file, header=True, index=False, sep='|', quoting=csv.QUOTE_NONE, escapechar="\\")
