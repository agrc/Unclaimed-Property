#!/usr/bin/env python
# * coding: utf8 *
"""
jobs.py
A module that creates the container metadata for it's job
"""

from pathlib import Path
from shutil import rmtree
from string import Template

JOB_TEMPLATE = Template(
    """
apiVersion: batch/v1
kind: Job
metadata:
  # Unique key of the Job instance
  name: geocoder-job-$job_number
spec:
  backoffLimit: 4
  template:
    metadata:
      name: geocoder-job-$job_number
      labels:
        jobtype: geocode
    spec:
      restartPolicy: Never
      volumes:
      - name: cloud-storage-key
        secret:
          secretName: gcs-key
      containers:
      - name: geocoder-client
        resources:
          limits:
            cpu: "100m"
            memory: "150Mi"
          requests:
            cpu: "50m"
            memory: "50Mi"
        image: gcr.io/agrc-204220/webapi/geocode-job
        imagePullPolicy: Always
        volumeMounts:
        - name: cloud-storage-key
          mountPath: /var/secrets/google
        env:
        - name: GOOGLE_APPLICATION_CREDENTIALS
          value: /var/secrets/google/key.json
        command: ["python"]
        args: ["/usr/local/geocode-job/geocode.py",
            "geocode", "$csv_name",
            "--from-bucket", "$upload_bucket",
            "--output-bucket", "$results_bucket"]
        # Do not restart containers after they exit
        """
)


def create_jobs(input_path, output_path):
    """the main method to call when the script is run
    """
    chunks = sorted(Path(input_path).glob('*.csv'))

    for i, path in enumerate(chunks):
        print(f'writing job for {path}')

        jobs = Path(output_path)

        if jobs.exists() and i == 0:
            rmtree(jobs)

        jobs.mkdir(parents=True, exist_ok=True)

        jobs = jobs.joinpath(f'job_{i}.yml')
        jobs.touch(exist_ok=False)

        with open(jobs, 'w') as yml:
            yml.write(
                JOB_TEMPLATE.substitute({
                    'job_number': i,
                    'upload_bucket': 'geocoder-csv-storage-95728',
                    'results_bucket': 'geocoder-csv-results-98576',
                    'csv_name': f'partition_{i}.csv',
                    'id_field': 'id',
                    'address_field': 'address',
                    'zone_field': 'zone'
                })
            )
