#!/usr/bin/env python
# * coding: utf8 *
"""
jobs.py
A module that creates the container metadata for it's job
"""

from pathlib import Path
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
            cpu: "50m"
            memory: "100Mi"
          requests:
            cpu: "50m"
            memory: "50Mi"
        image: gcr.io/ut-dts-agrc-geocoding-dev/api.mapserv.utah.gov/geocode-job
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
            "--output-bucket", "$results_bucket",
            "--ignore-failure", "true"]
        # Do not restart containers after they exit
        """
)


def job_sort_function(path):
    """sort the jobs by the job number
    """
    return int(path.stem.split('_')[1])


def create_jobs(input_path, output_path):
    """the main method to call when the script is run
    """
    chunks = sorted(Path(input_path).glob('*.csv'), key=job_sort_function)

    _ = [job.unlink() for job in Path(output_path).glob('*.yml')]

    for i, path in enumerate(chunks):
        print(f'writing job for {path}')

        jobs = Path(output_path)

        jobs = jobs / f'job_{path.stem}.yml'

        with open(jobs, 'w', encoding='utf-8') as yml:
            yml.write(
                JOB_TEMPLATE.substitute({
                    'job_number': i,
                    'upload_bucket': 'ut-dts-agrc-geocoding-dev-source',
                    'results_bucket': 'ut-dts-agrc-geocoding-dev-result',
                    'csv_name': path.name,
                    'id_field': 'id',
                    'address_field': 'address',
                    'zone_field': 'zone'
                })
            )
