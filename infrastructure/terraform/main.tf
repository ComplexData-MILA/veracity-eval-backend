terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
  backend "gcs" {
    bucket = "misinformation-mitigation-terraform-state"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_compute_network" "vpc_network" {
  name                    = "misinformation-mitigation-vpc-network"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  name          = "misinformation-mitigation-subnet"
  ip_cidr_range = "10.2.0.0/16"
  region        = var.region
  network       = google_compute_network.vpc_network.id
}

resource "google_compute_global_address" "private_ip_address" {
  name          = "misinformation-mitigation-private-ip"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc_network.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc_network.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_address.name]
}

resource "google_container_cluster" "primary" {
  name     = "misinformation-mitigation-gke-cluster"
  location = "${var.region}-a"

  remove_default_node_pool = true
  initial_node_count       = 1

  network    = google_compute_network.vpc_network.name
  subnetwork = google_compute_subnetwork.subnet.name

  depends_on = [google_service_networking_connection.private_vpc_connection]
}

resource "google_container_node_pool" "primary_nodes" {
  name       = "misinformation-mitigation-node-pool"
  location   = "${var.region}-a"
  cluster    = google_container_cluster.primary.name
  node_count = 1

  node_config {
    preemptible  = false
    machine_type = "e2-medium"

    service_account = google_service_account.gke_sa.email
    oauth_scopes    = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }

  depends_on = [google_service_networking_connection.private_vpc_connection]
}

resource "google_service_account" "gke_sa" {
  account_id   = "misinfo-mitigation-gke-sa"
  display_name = "GKE Service Account"
}

resource "google_project_iam_member" "gke_sa_roles" {
  project = var.project_id
  role    = "roles/container.developer"
  member  = "serviceAccount:${google_service_account.gke_sa.email}"
}

resource "google_sql_database_instance" "misinformation-mitigation_db" {
  name             = "misinformation-mitigation-db"
  database_version = "POSTGRES_13"
  region           = var.region

  depends_on = [google_service_networking_connection.private_vpc_connection]

  settings {
    tier = "db-f1-micro"

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc_network.id
    }

    backup_configuration {
      enabled = true
    }
  }

  deletion_protection = false
}

resource "google_sql_database" "misinformation-mitigation_database" {
  name     = "misinformation_mitigation_db"
  instance = google_sql_database_instance.misinformation-mitigation_db.name
}

resource "google_sql_user" "misinformation-mitigation_user" {
  name     = "misinformation_mitigation_user"
  instance = google_sql_database_instance.misinformation-mitigation_db.name
  password = var.db_password
}

resource "google_compute_global_address" "api_ip" {
  name         = "misinformation-mitigation-api-ip"
  address_type = "EXTERNAL"
}

resource "google_dns_managed_zone" "veri_fact_ai" {
  name        = "veri-fact-ai"
  dns_name    = "veri-fact.ai."
  description = "Veri-Fact.ai DNS zone"
}

resource "google_dns_record_set" "api" {
  name         = "api.${google_dns_managed_zone.veri_fact_ai.dns_name}"
  managed_zone = google_dns_managed_zone.veri_fact_ai.name
  type         = "A"
  ttl          = 300

  rrdatas = [google_compute_global_address.api_ip.address]
}

variable "project_id" {
  description = "The project ID to deploy to"
  default     = "misinformation-mitigation"
}

variable "region" {
  description = "The region to deploy resources"
  default     = "northamerica-northeast1"
}

variable "db_password" {
  description = "The password for the database user"
  sensitive   = true
}

output "kubernetes_cluster_name" {
  value       = google_container_cluster.primary.name
  description = "GKE Cluster Name"
}

output "database_connection_name" {
  value = "misinformation-mitigation:northamerica-northeast1:misinformation-mitigation-db"
}

output "api_ip_address" {
  value       = google_compute_global_address.api_ip.address
  description = "The IP address for the API"
}