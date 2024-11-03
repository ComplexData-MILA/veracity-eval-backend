# Provider configuration
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

# Get GKE cluster info
data "google_container_cluster" "my_cluster" {
  name     = google_container_cluster.primary.name
  location = google_container_cluster.primary.location
}

# Configure kubernetes provider with cluster access token
data "google_client_config" "default" {}

provider "kubernetes" {
  host                   = "https://${data.google_container_cluster.my_cluster.endpoint}"
  token                  = data.google_client_config.default.access_token
  cluster_ca_certificate = base64decode(data.google_container_cluster.my_cluster.master_auth[0].cluster_ca_certificate)
}

# Network resources
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

# GKE Cluster
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
}

resource "google_container_node_pool" "primary_nodes" {
  name     = "misinformation-mitigation-node-pool"
  location = "${var.region}-a"
  cluster  = google_container_cluster.primary.name

  initial_node_count = 1

  autoscaling {
    min_node_count = 1
    max_node_count = 3
  }

  upgrade_settings {
    max_surge       = 1
    max_unavailable = 0
    strategy        = "SURGE"
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    preemptible  = false
    machine_type = "e2-medium"

    labels = {
      environment = "production",
      app         = "misinformation-mitigation"
    }

    service_account = google_service_account.gke_sa.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    tags            = ["gke-misinformation-mitigation-gke-cluster"]

    workload_metadata_config {
      mode = "GKE_METADATA"
    }
  }
}

resource "google_compute_firewall" "allow_http_https" {
  name    = "allow-http-https"
  network = google_compute_network.vpc_network.name

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["gke-misinformation-mitigation-gke-cluster"]
}


# Service Account for GKE
resource "google_service_account" "gke_sa" {
  account_id   = "misinfo-mitigation-gke-sa"
  display_name = "GKE Service Account"
}

resource "google_project_iam_member" "gke_sa_roles" {
  for_each = toset([
    "roles/container.developer",
    "roles/cloudsql.client",
    "roles/cloudsql.instanceUser",
    "roles/storage.objectViewer"
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.gke_sa.email}"
}

# Cloud SQL
resource "google_compute_global_address" "private_ip_address" {
  name          = "private-ip-address"
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

resource "google_sql_database_instance" "misinformation_mitigation_db" {
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
  }

  deletion_protection = false
}

resource "google_sql_database" "misinformation_mitigation_database" {
  name     = "misinformation_mitigation_db"
  instance = google_sql_database_instance.misinformation_mitigation_db.name
}

resource "google_sql_user" "misinformation_mitigation_user" {
  name     = "misinformation_mitigation_user"
  instance = google_sql_database_instance.misinformation_mitigation_db.name
  password = var.db_password
}

# Kubernetes Resources
resource "kubernetes_namespace" "misinformation_mitigation" {
  metadata {
    name = "misinformation-mitigation"
  }
}

resource "kubernetes_service_account" "workload_identity_sa" {
  metadata {
    name      = "workload-identity-sa"
    namespace = kubernetes_namespace.misinformation_mitigation.metadata[0].name
    annotations = {
      "iam.gke.io/gcp-service-account" = google_service_account.gke_sa.email
    }
  }
}

resource "google_service_account_iam_binding" "workload_identity_sa_binding" {
  service_account_id = google_service_account.gke_sa.name
  role               = "roles/iam.workloadIdentityUser"

  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[${kubernetes_namespace.misinformation_mitigation.metadata[0].name}/${kubernetes_service_account.workload_identity_sa.metadata[0].name}]",
  ]
}

resource "kubernetes_deployment" "misinformation_mitigation_api" {
  metadata {
    name      = "misinformation-mitigation-api"
    namespace = kubernetes_namespace.misinformation_mitigation.metadata[0].name
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

        annotations = {
          "timestamp" = timestamp() // Force redeployment
        }
      }

      spec {
        service_account_name = kubernetes_service_account.workload_identity_sa.metadata[0].name

        container {
          image = "gcr.io/${var.project_id}/misinformation-mitigation-api:latest"
          name  = "misinformation-mitigation-api"

          env {
            name  = "DATABASE_URL"
            value = "postgresql://misinformation_mitigation_user:${var.db_password}@127.0.0.1:5432/misinformation_mitigation_db"
          }

          env {
            name  = "GOOGLE_APPLICATION_CREDENTIALS"
            value = "/app/service-account.json"
          }

          volume_mount {
            name       = "service-account-key"
            mount_path = "/app/service-account.json"
            sub_path   = "service-account.json"
          }


          port {
            container_port = 8001
          }

          readiness_probe {
            http_get {
              path = "/v1/health"
              port = 8001
            }
            initial_delay_seconds = 10
            period_seconds        = 5
          }
        }

        container {
          name  = "cloud-sql-proxy"
          image = "gcr.io/cloudsql-docker/gce-proxy:1.33.1"
          command = [
            "/cloud_sql_proxy",
            "-instances=${var.project_id}:${var.region}:${google_sql_database_instance.misinformation_mitigation_db.name}=tcp:5432",
            "-ip_address_types=PRIVATE"
          ]

          security_context {
            run_as_non_root = true
          }
        }

        volume {
          name = "service-account-key"
          secret {
            secret_name = "vertex-ai-credentials"
            items {
              key  = "service-account.json"
              path = "service-account.json"
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "misinformation_mitigation_api" {
  metadata {
    name      = "misinformation-mitigation-api"
    namespace = kubernetes_namespace.misinformation_mitigation.metadata[0].name
  }

  spec {
    selector = {
      app = kubernetes_deployment.misinformation_mitigation_api.spec[0].template[0].metadata[0].labels.app
    }

    port {
      port        = 80
      target_port = 8001
    }
    type = "NodePort"
  }
}


# Load Balancer and DNS
resource "google_compute_global_address" "misinformation_mitigation_api_ip" {
  name = "misinformation-mitigation-api-ip"
}

resource "google_compute_managed_ssl_certificate" "misinformation_mitigation_cert" {
  name = "misinformation-mitigation-cert"
  managed {
    domains = ["api.veri-fact.ai"]
  }
}

resource "kubernetes_ingress_v1" "misinformation_mitigation_ingress" {
  metadata {
    name      = "misinformation-mitigation-ingress"
    namespace = kubernetes_namespace.misinformation_mitigation.metadata[0].name
    annotations = {
      "kubernetes.io/ingress.class"                 = "gce"
      "kubernetes.io/ingress.global-static-ip-name" = google_compute_global_address.misinformation_mitigation_api_ip.name
      "networking.gke.io/managed-certificates"      = "misinformation-mitigation-cert"
      "kubernetes.io/ingress.allow-http"            = "false"
      "ingress.gcp.kubernetes.io/pre-shared-cert"   = google_compute_managed_ssl_certificate.misinformation_mitigation_cert.name
      "kubernetes.io/ingress.force-ssl-redirect"    = "true"
    }
  }
  spec {
    default_backend {
      service {
        name = kubernetes_service.misinformation_mitigation_api.metadata[0].name
        port {
          number = 80
        }
      }
    }
    rule {
      host = "api.veri-fact.ai"
      http {
        path {
          path      = "/"
          path_type = "Prefix"
          backend {
            service {
              name = kubernetes_service.misinformation_mitigation_api.metadata[0].name
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

resource "kubernetes_manifest" "managed_certificate" {
  manifest = {
    apiVersion = "networking.gke.io/v1"
    kind       = "ManagedCertificate"
    metadata = {
      name      = "misinformation-mitigation-cert"
      namespace = kubernetes_namespace.misinformation_mitigation.metadata[0].name
    }
    spec = {
      domains = ["api.veri-fact.ai"]
    }
  }
}

resource "google_dns_managed_zone" "veri_fact_ai" {
  name        = "veri-fact-ai-zone"
  dns_name    = "veri-fact.ai."
  description = "DNS zone for veri-fact.ai"
}

resource "google_dns_record_set" "api" {
  name         = "api.${google_dns_managed_zone.veri_fact_ai.dns_name}"
  managed_zone = google_dns_managed_zone.veri_fact_ai.name
  type         = "A"
  ttl          = 300

  rrdatas = [google_compute_global_address.misinformation_mitigation_api_ip.address]
}

# Variables
variable "project_id" {
  description = "The project ID to deploy to"
  default     = "misinformation-mitigation"
}

variable "region" {
  description = "The region to deploy to"
  default     = "northamerica-northeast1"
}

variable "db_password" {
  description = "Database password"
  sensitive   = true
}

# Outputs
output "kubernetes_cluster_name" {
  value       = google_container_cluster.primary.name
  description = "GKE Cluster Name"
}

output "database_connection_name" {
  value = google_sql_database_instance.misinformation_mitigation_db.connection_name
}

output "api_ip_address" {
  value       = google_compute_global_address.misinformation_mitigation_api_ip.address
  description = "The IP address for the API"
}

resource "google_project_iam_member" "user_project_owner" {
  project = var.project_id
  role    = "roles/owner"
  member  = "user:wgarneau@veri-fact.ai"
}

resource "kubernetes_cluster_role_binding" "user_cluster_admin" {
  metadata {
    name = "user-cluster-admin"
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = "cluster-admin"
  }
  subject {
    kind      = "User"
    name      = var.user_email
    api_group = "rbac.authorization.k8s.io"
  }
}

resource "kubernetes_role_binding" "user_namespace_admin" {
  metadata {
    name      = "user-namespace-admin"
    namespace = kubernetes_namespace.misinformation_mitigation.metadata[0].name
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = "admin"
  }
  subject {
    kind      = "User"
    name      = var.user_email
    api_group = "rbac.authorization.k8s.io"
  }
}

variable "user_email" {
  description = "Email of the user to grant permissions"
  default     = "wgarneau@veri-fact.ai"
}
