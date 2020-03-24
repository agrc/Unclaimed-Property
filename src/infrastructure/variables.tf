variable app_version {
  type        = string
  description = "Current version"
  default     = "1-0-0"
}

variable project_id {
  type        = string
  description = "The project ID to manage the cloud geocoding resources"
  default     = "agrc-204220"
}

variable region {
  type        = string
  description = "The region of the cloud resources"
  default     = "us-central1"
}

variable zone {
  type        = string
  description = "The zone of the cloud resources"
  default     = "us-central1-a"
}

variable name {
  type        = string
  description = "The name of the cloud resource"
  default     = "cloud-geocoding"
}

variable machine_type {
  type        = string
  description = "The compute machine size"
  default     = "n1-standard-4"
}

variable user_labels {
  description = "The standard DTS labels for billing"
  type        = map(string)
  default = {
    app        = "cloud-geocoding"
    supportcod = "tbd"
    elcid      = "itagrc"
    contact    = "steve-gourley"
    dept       = "agr"
    env        = "prod"
    security   = "tbd"
  }
}

variable boot_image {
  description = "The image to use when starting a compute vm"
  type = string
  default = "cloud-geocoding-v1-0-0"
}

variable agrc_cidrs  {
    description = "The agrc office and VPN cidr"
    type = list(string)
}
