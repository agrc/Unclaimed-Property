# Large Scale Geocoding

## Create infrastructure

1. Run the cloud-geocoding terraform in the gcp-terraform monorepo
1. Make sure the [boot image](https://console.cloud.google.com/compute/images) is current.

```tf
  boot_disk {
    initialize_params {
      image = "arcgis-server-geocoding"
    }
  }
```

1. Update `deployment.yml` with the private/internal ip address of the compute vm created above. If it is different than what is in your `deployment.yml`, run `terraform apply` again to correct the kubernetes cluster.

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

1. Use the CLI to upload the files to the cloud so they are accessible to the kubernetes cluster containers

   ```sh
   python -m cli upload
   ```

1. Use the CLI to create `yml` job files to apply to the kubernetes cluster nodes to start the jobs. By default the job specifications will be created in the `jobs` folder.

   ```sh
   python -m cli create jobs
   ```

## Secrets

1. Create a `secret.yml` file from the `secret.yml.sample` file and add the base64 key from a service worker with access to google cloud storage. The following command will put the base64 into your clipboard.

   ```sh
   base64 path/to/service-account.json | pbcopy
   ```

1. Push this secret to the kubernetes cluster

   ```sh
   kubectl apply -f secret.yml
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

## Enhance

### Geocode Results

Download the csv output from cloud storage and place them in `data/geocode-results`. Rename them to be compatible with a file geodatabase.

### Enhance Geodatabase

The geocode results will be enhanced from spatial data. The cli is used to create the gdb for this processing. The layers are defined in `enhance.py` and are copied from the OpenSGID.

```sh
python -m cli create enhancement-gdb
```

Enhance the csv's in the `data\geocoded-results` folder. Depending on the number of enhancement layers, you will end up with a `partition_number_step_number.csv`.

```sh
python -m cli enhance
```

To merge all the data back together into one `data\results\all.csv`

```sh
python -m cli merge
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

You can create jobs for the `postmortem` folder and upload the data to try the files again.

It is recommended to run `all_errors.csv` and `post-mortem` those result. Make sure to update the job to allow for `--ignore-failures` or it will most likely fast fail. Then `post-mortem normalize` the results and run those again to be thorough.

## Maintenance

### VM updates

1. RDP into the machine and install the most current locators. (google drive link or gcp bucket)
1. Might as well install windows updates
1. Save a [snapshot](https://console.cloud.google.com/compute/snapshots) `cloud-geocoding-v1-0-0`
1. Create an [image](https://console.cloud.google.com/compute/images) from the snapshot `cloud-geocoding-v1-0-0`

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
