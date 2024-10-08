terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
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

provider "kubernetes" {
  host                   = "https://${google_container_cluster.primary.endpoint}"
  token                  = data.google_client_config.default.access_token
  cluster_ca_certificate = base64decode(google_container_cluster.primary.master_auth[0].cluster_ca_certificate)
}

data "google_client_config" "default" {}

resource "google_compute_network" "vpc_network" {
  name                    = "misinformation-mitigation-vpc-network"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  name          = "misinformation-mitigation-subnet"
  ip_cidr_range = "10.2.0.0/16"
  region        = var.region
  network       = google_compute_network.vpc_network.id

  secondary_ip_range {
    range_name    = "pod-ranges"
    ip_cidr_range = "10.20.0.0/16"
  }

  secondary_ip_range {
    range_name    = "services-ranges"
    ip_cidr_range = "10.30.0.0/16"
  }
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

  ip_allocation_policy {
    cluster_secondary_range_name  = "pod-ranges"
    services_secondary_range_name = "services-ranges"
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  master_authorized_networks_config {
    cidr_blocks {
      cidr_block   = "0.0.0.0/0"
      display_name = "All"
    }
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

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
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]

    workload_metadata_config {
      mode = "GKE_METADATA"
    }
  }
}

resource "google_compute_firewall" "allow_internal" {
  name    = "allow-internal"
  network = google_compute_network.vpc_network.name

  allow {
    protocol = "tcp"
  }
  allow {
    protocol = "udp"
  }
  allow {
    protocol = "icmp"
  }

  source_ranges = ["10.2.0.0/16", "10.20.0.0/16", "10.30.0.0/16"]
}

resource "google_compute_router" "router" {
  name    = "nat-router"
  network = google_compute_network.vpc_network.name
  region  = var.region
}

resource "google_compute_router_nat" "nat" {
  name                               = "nat-config"
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}

resource "google_service_account" "gke_sa" {
  account_id   = "misinfo-mitigation-gke-sa"
  display_name = "GKE Service Account"
}

resource "google_project_iam_member" "gke_sa_roles" {
  for_each = toset([
    "roles/container.developer",
    "roles/cloudsql.client",
    "roles/storage.objectViewer"
  ])
  
  project = var.project_id
  role    = each.key
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

data "kubernetes_service_account" "misinformation-mitigation-api" {
  metadata {
    name      = "misinformation-mitigation-api"
    namespace = "default"
  }
}

resource "kubernetes_annotations" "service_account_annotation" {
  api_version = "v1"
  kind        = "ServiceAccount"
  metadata {
    name      = "misinformation-mitigation-api"
    namespace = "default"
  }
  annotations = {
    "iam.gke.io/gcp-service-account" = google_service_account.gke_sa.email
  }
}

resource "kubernetes_deployment" "misinformation-mitigation-api" {
  metadata {
    name      = "misinformation-mitigation-api"
    namespace = "default"
    labels = {
      app = "misinformation-mitigation-api"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "misinformation-mitigation-api"
      }
    }

    template {
      metadata {
        labels = {
          app = "misinformation-mitigation-api"
        }
      }

      spec {
        service_account_name = data.kubernetes_service_account.misinformation-mitigation-api.metadata[0].name

        container {
          image = "gcr.io/${var.project_id}/misinformation-mitigation-api:latest"
          name  = "misinformation-mitigation-api"

          env {
            name  = "DATABASE_URL"
            value = "postgresql://misinformation_mitigation_user:${var.db_password}@127.0.0.1:5432/misinformation_mitigation_db"
          }

          port {
            container_port = 8001
          }

          lifecycle {
            post_start {
              exec {
                command = ["/bin/sh", "-c", "alembic upgrade head"]
              }
            }
          }
        }

        container {
          name  = "cloud-sql-proxy"
          image = "gcr.io/cloudsql-docker/gce-proxy:1.33.1"
          
          command = [
            "/cloud_sql_proxy",
            "-instances=${var.project_id}:${var.region}:${google_sql_database_instance.misinformation-mitigation_db.name}=tcp:5432",
            "-ip_address_types=PRIVATE"
          ]

          security_context {
            run_as_non_root = true
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      spec[0].template[0].spec[0].container[0].image,
      spec[0].template[0].spec[0].container[1].image,
      metadata[0].annotations
    ]
  }
}

resource "kubernetes_service" "misinformation-mitigation-api-service" {
  metadata {
    name      = "misinformation-mitigation-api-service"
    namespace = "default"
  }
  spec {
    selector = {
      app = kubernetes_deployment.misinformation-mitigation-api.metadata[0].labels.app
    }
    port {
      port        = 80
      target_port = 8001
    }
    type = "NodePort"
  }
}

resource "kubernetes_ingress_v1" "misinformation-mitigation-api-ingress" {
  metadata {
    name      = "misinformation-mitigation-api-ingress"
    namespace = "default"
    annotations = {
      "kubernetes.io/ingress.class"                 = "gce"
      "kubernetes.io/ingress.global-static-ip-name" = google_compute_global_address.api_ip.name
      "networking.gke.io/managed-certificates"      = "misinformation-mitigation-api-cert"
      "kubernetes.io/ingress.allow-http"            = "false"
    }
  }

  spec {
    rule {
      host = "api.veri-fact.ai"
      http {
        path {
          path = "/*"
          path_type = "Prefix"
          backend {
            service {
              name = kubernetes_service.misinformation-mitigation-api-service.metadata[0].name
              port {
                number = 80
              }
            }
          }
        }
      }
    }
  }
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
  value = "${var.project_id}:${var.region}:${google_sql_database_instance.misinformation-mitigation_db.name}"
}

output "api_ip_address" {
  value       = google_compute_global_address.api_ip.address
  description = "The IP address for the API"
}