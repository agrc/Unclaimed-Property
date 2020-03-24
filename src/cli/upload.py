#!/usr/bin/env python
# * coding: utf8 *
'''
upload.py
A module that uploads the partitioned data to google cloud storage
'''
from pathlib import Path

from google.cloud import storage


def upload_files(source_file_name, bucket_name):
    '''the main method to be called when the script is invoked
    '''
    print(f'uploading {source_file_name} to {bucket_name}')
    storage_client = storage.Client().from_service_account_json('gcs-sa.json')

    name = Path(source_file_name).name
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(name)

    blob.upload_from_filename(source_file_name)
