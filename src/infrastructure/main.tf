// Kubernetes

resource "google_container_cluster" "cloud_geocoding_cluster" {
  name = "cloud-geocoding"
  location = var.zone
  initial_node_count = 3
  network = google_compute_network.vpc_network.name
  # You must set local gcloud cli to the correct account for this to work
  # gcloud config get-value account
  provisioner "local-exec" {
      working_dir="./"
      command = <<EOF
      gcloud config set project ${var.project_id} && \
      gcloud config set compute/zone ${var.zone} && \
      gcloud container clusters get-credentials cloud-geocoding && \
      kubectl create configmap app-config --from-file=appsettings.json=webapi.json && \
      kubectl apply -f deployment.yml
EOF
  }
}

// Virtual Machine

resource "google_compute_instance" "agrc_geocoding_vm" {
  name         = "${var.name}-v${var.app_version}"
  machine_type = var.machine_type
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = var.boot_image
    }
  }

  network_interface {
    network = google_compute_network.vpc_network.name
    access_config {
    }
  }
}

// Networking

resource "google_compute_network" "vpc_network" {
  name                    = "arcgis"
  auto_create_subnetworks = "true"
  description             = "Network for AGRC Geocoding"
}

// Firewall

resource "google_compute_firewall" "arcgis_server_allow_internal" {
  name        = "${google_compute_network.vpc_network.name}-allow-internal"
  network     = google_compute_network.vpc_network.name
  description = "Allow internal traffic on the default network"
  priority    = "65534"
  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "icmp"
  }
  source_ranges = ["10.128.0.0/9"]
}

resource "google_compute_firewall" "arcgis_server" {
  name    = "${google_compute_network.vpc_network.name}-allow-arcgis"
  network = google_compute_network.vpc_network.name

  description = "Allow all traffic to both ArcGIS Server ports"
  allow {
    protocol = "tcp"
    ports    = ["6080", "6443"]
  }
  source_ranges = ["0.0.0.0/0"]
}

resource "google_compute_firewall" "arcgis_server_vm_rdp" {
  name        = "${google_compute_network.vpc_network.name}-allow-rdp"
  network     = google_compute_network.vpc_network.name
  description = "Allow RDP AGRC Office/DTS-AGRC VPN Group"
  priority    = "65534"
  allow {
    protocol = "tcp"
    ports    = ["3389"]
  }
  source_ranges = var.agrc_cidrs
}
