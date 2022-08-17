# Large Scale Geocoding

## Create infrastructure

1. Run the `batch-geocoding` terraform in the gcp-terraform monorepo
1. Make sure the [boot image](https://console.cloud.google.com/compute/images) is current.

```tf
  boot_disk {
    initialize_params {
      image = "arcgis-server-geocoding"
    }
  }
```

1. Update `deployment.yml` from the terraform repo with the private/internal ip address of the compute vm created above. If it is different than what is in your `deployment.yml`, run `kubectl apply -f deployment.yml` again to correct the kubernetes cluster.

### Infrastructure parts

#### Google cloud compute

A Windows virtual machine runs ArcGIS Server with the geocoding services to support the geocoding jobs.

#### Geocoding job container

A docker container containing a python script to execute the geocoding with data uploaded to google cloud.

## Prepare the data

1. Use the CLI to split the address data into chunks. By default they will be created in the `data\partitioned` folder.

   ```sh
   python -m cli create partitions --input-csv=../data/2022.csv --separator=\| --column-names=category --column-names=partial-id --column-names=address --column-names=zone
   ```

   The CSV will contain 4 fields without a header row. They will be pipe delimited without quoting. They will be in the order `system-area`, `system-id`, `address`, `zip-code`. This CLI command will merge `system-area` and `system-id` into an `id` field and rename `zip-code` to `zone`.

1. Use the CLI to upload the files to the cloud so they are accessible to the kubernetes cluster containers

   ```sh
   python -m cli upload
   ```

1. Use the CLI to create `yml` job files to apply to the kubernetes cluster nodes to start the jobs. By default the job specifications will be created in the `jobs` folder.

   ```sh
   python -m cli create jobs
   ```

## Start the job

To start the job, you must apply the `jobs/job_*.yml` to the cluster. Run this command for each `job.yml` file that you created.

```sh
kubectl apply -f job.yaml
```

## Monitor the jobs

cloud logging [log viewer](https://console.cloud.google.com/logs/)

- python geocoding process

  ```js
  resource.type="k8s_container"
  resource.labels.project_id="ut-dts-agrc-geocoding-dev"
  resource.labels.location="us-central1-a"
  resource.labels.cluster_name="cloud-geocoding"
  resource.labels.namespace_name="default"
  resource.labels.pod_name:"geocoder-job-"
  resource.labels.container_name="geocoder-client"
  ```

- web api process

  ```js
  resource.type="k8s_container"
  resource.labels.project_id="ut-dts-agrc-geocoding-dev"
  resource.labels.location="us-central1-a"
  resource.labels.cluster_name="cloud-geocoding"
  resource.labels.namespace_name="default"
  resource.labels.pod_name:"webapi-api-"
  resource.labels.container_name="webapi-api"
  ```

kubernetes [workloads](https://console.cloud.google.com/kubernetes/workload)

### Geocode Results

Download the csv output from cloud storage and place them in `data/geocoded-results`. `gsutil` can be run from the root of the project to download all the files.

```sh
gsutil -m cp "gs://ut-dts-agrc-geocoding-dev-result/*.csv" ./../data/geocoded-results
```

### Post mortem

It is a good idea to make sure all the addresses that were not found were not caused by something else.

```sh
python -m cli post-mortem
```

This will create the following files

- `all_errors.csv`: all of the unmatched addresses from the geocoded results
- `api_errors.csv`: a subset of `all_errors.csv` where the message is not a normal api response
- `all_errors_job.csv`: all of the unmatched addresses from the geocoded results but in a format that can be processed by the cluster.
- `incomplete_errors.csv`: typically errors that have null parts. This should be inspected because other errors can get mixed in here
- `not_found.csv`: all the addresses that 404'd as not found by the api. `post-mortem normalize` will run these addresses through sweeper.

#### First post mortem round

It is recommended to run `all_errors_job.csv` and `post-mortem` those result to get a more accurate geocoding job picture. Make sure to update the job to allow for `--ignore-failures` or it will most likely fast fail.

1. Create the job for the `postmortem` and upload the data to geocode the error results again.

  ```sh
  python -m cli create jobs --input-jobs=./../data/postmortem --single=all_errors_job.csv
  ```

1. Upload the data for the job

  ```sh
  python -m cli upload --single=./../data/postmortem/all_errors_job.csv
  ```

1. Apply the job in the kubernetes cluster

  ```sh
  kubectl apply -f ./../jobs/job_all_errors_job.yml
  ```

1. When that job has completed you can download the results with `gsutil`

  ```sh
  gsutil cp -n "gs://ut-dts-agrc-geocoding-dev-result/*-all_errors_job.csv" ./../data/geocoded-results
  ```

1. Finally, rebase the results back into the original data with the cli

  ```sh
  python -m cli post-mortem rebase --single="*-all_errors_job.csv"
  ```

Now, the original data is updated with this new runs results to fix any hiccups with the original geocode attempt.

#### Second post mortem round

The second post mortem round is to see if we can correct the addresses of the records that do not match using the sweeper project.

1. We need to remove the results of the first round so they do not get processed. Delete the `*-all_errors_job.csv` from the `data/geocoded-results` folder.

1. Post mortem the results to get the current state.

  ```sh
  python -m cli post-mortem
  ```

1. Try to fix the unmatched addresses with sweeper.

  ```sh
  python -m cli post-mortem normalize
  ```

1. Create a job for the normalized addresses

  ```sh
  python -m cli create jobs --input-jobs=./../data/postmortem --single=normalized.csv
  ```

1. Upload the data for the job

  ```sh
  python -m cli upload --input-folder=./../data/postmortem --single=normalized.csv
  ```

1. Apply the job in the kubernetes cluster

  ```sh
  kubectl apply -f ./../jobs/job_normalized.yml
  ```

1. When that job has completed you can download the results with `gsutil`

  ```sh
  gsutil cp "gs://ut-dts-agrc-geocoding-dev-result/*-normalized.csv" ./../data/geocoded-results
  ```

1. Rebase the results back into the original data with the cli

  ```sh
  python -m cli post-mortem rebase --single="*-normalized.csv" --message="sweeper modified input address from original"
  ```

1. Finally, remove the normalized csv and run post mortem one last time to get synchronize reality

  ```sh
  python -m cli post-mortem
  ```

### Enhance Geodatabase

The geocode results will be enhanced from spatial data. The cli is used to create the gdb for this processing. The layers are defined in `enhance.py` and are copied from the OpenSGID.

1. The geocoded results will need to be renamed to be compatible with a file geodatabase.

  ```sh
  python -m cli rename
  ```

1. Create the enhancement geodatabase

  ```sh
  python -m cli create enhancement-gdb
  ```

1. Enhance the csv's in the `data\geocoded-results` folder. Depending on the number of enhancement layers, you will end up with a `partition_number_step_number.csv`.

  ```sh
  python -m cli enhance
  ```

1. Merge all the data back together into one `data\results\all.csv`

  ```sh
  python -m cli merge
  ```

### Create Deliverable

## Maintenance

### VM updates

1. RDP into the machine and install the most current locators. (google drive link or gcp bucket)
1. Create a Cloud NAT and Router to get internet access to the machine
1. Might as well install windows updates
1. Update the locators (There is a geolocators shortcut on the desktop to where they are)
   - I typically compare the dates and grab the `.loc` and `.lox` from the web api machine and copy them over
1. Save a [snapshot](https://console.cloud.google.com/compute/snapshots) `arcgis-server-geocoding-M-YYYY`
   - Source disk is `cloud-geocoding-v1`
   - Region `is us-central1`
   - Delete the other snapshots besides the original
1. Create an [image](https://console.cloud.google.com/compute/images) from the snapshot `arcgis-server-geocoding-M-YYY`

### geocoding job container

The geocoding job docker image installs the `geocode.py` file into the container and installs the python dependencies for the script. When the `job.yml` files are applied to the cluster, the `geocode.py` script is executed which starts the geocoding job.

Any time the `geocode.py` file is modified or you want to update the python dependencies, the docker image needs to be rebuilt and pushed to gcr. With `src/docker-geocode-job` as your current working directory...

```sh
docker build . --tag webapi/geocode-job &&
docker tag webapi/geocode-job:latest gcr.io/ut-dts-agrc-geocoding-dev/api.mapserv.utah.gov/geocode-job:latest &&
docker push gcr.io/ut-dts-agrc-geocoding-dev/api.mapserv.utah.gov/geocode-job:latest
```

To locally test the geocode.py try a command like

```sh
python geocode.py geocode partition_7.csv --from-bucket=../../../data/partitioned --output-bucket=./ --testing=true
```
