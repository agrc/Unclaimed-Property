# Large Scale Geocoding

## Create infrastructure

1. Create a `terraform.tfvars` file from the `tfvars.sample` and fill out the values
1. Make sure the `prod.tfvars` has the most current [boot image](https://console.cloud.google.com/compute/images).

```tf
  boot_image = "cloud-geocoding-v1-0-0
```

1. With `src/infrastructure` as your current working directory, run `terraform apply` to create the cloud infrastructure. If this is the first run, execute `terraform init` to download the terraform dependencies. The terraform output will print the private ip.
1. Update `infrastructure/deployment.yml` with the private/internal ip address of the compute vm created above. If it is different than what is in your `deployment.yml`, run `terraform apply` again to correct the kubernetes cluster.

### Infrastructure parts

#### Google cloud compute

A Windows virtual machine runs ArcGIS Server with the geocoding services to support the geocoding jobs.

#### Geocoding job container

A docker container containing a python script to execute the geocoding with data uploaded to google cloud.

## Prepare the data

1. Use the CLI to split the address data into chunks

    ```sh
    python -m cli create partitions --input-csv=../data/2020-03-09.csv --separator=\| --column-names=category --column-names=partial-id --column-names=address --column-names=zone
    ```

1. Use the CLI to create `yml` job files to apply to the kubernetes cluster nodes to start the jobs

    ```sh
    python -m cli create jobs
    ```

1. Use the CLI to upload the files to the cloud so they are accessible to the kubernetes cluster containers

    ```sh
    python -m cli upload
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

To start the job, you mush apply the `jobs/job_*.yml` to the cluster. Run this command for each `job.yml` file that you created.

```sh
kubectl apply -f job.yaml
```

## Monitor the jobs

stack driver [log viewer](https://console.cloud.google.com/logs/)

```js
resource.type="k8s_container"
resource.labels.project_id="agrc-204220"
resource.labels.location="us-central1-a"
resource.labels.cluster_name="cloud-geocoding"
resource.labels.namespace_name="default"
resource.labels.pod_name:"geocoder-job-"
resource.labels.container_name="geocoder-client"
```

kubernetes [workloads](https://console.cloud.google.com/kubernetes/workload)

## Maintenance

### VM updates

1. RDP into the machine and install the most current locators. (google drive link or gcp bucket)
1. Might as well install windows updates
1. Save a [snapshot](https://console.cloud.google.com/compute/snapshots) `cloud-geocoding-v1-0-0`
1. Create an [image](https://console.cloud.google.com/compute/images) from the snapshot `cloud-geocoding-v1-0-0`

### geocoding job container

The geocoding job docker image installs the geocode.py file into the container and installs the python dependencies for the script. When the job yml files are applied to the container, the geocode.py script is executed which starts the geocoding job.

Any time the `geocode.py` file is modified or you want to update the python dependencies, the docker image needs to be rebuilt and pushed to gcr. With `src/docker-geocode-job` as your current working directory...

1. `docker build . --tag webapi/geocode-job`
1. `docker tag webapi/geocode-job:latest gcr.io/ut-dts-agrc-geocoding-dev/api.mapserv.utah.gov/geocode-job:latest`
1. `docker push gcr.io/ut-dts-agrc-geocoding-dev/api.mapserv.utah.gov/geocode-job:latest`

To locally test the geocode.py try a command like

```sh
python geocode.py geocode partition_7.csv --from-bucket=../../../data/partitioned --output-bucket=./ --testing=true
```

## Post Process

The `post-process/extract.py` file takes the partitioned result data and appends geographical data to it. Depending on the number of steps, you will end up with a `file_step_number_results.csv`. Execute from the `post-process` folder.

```sh
python extract.py enhance partition_5.csv --as=job_5
```

Zip all files and deliver
