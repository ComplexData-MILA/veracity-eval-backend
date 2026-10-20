# Dev environment: a copy of infrastructure/terraform/main.tf with "-dev" names,
# non-overlapping CIDRs and its own state. It never reads or writes prod state.
# Keep resource shapes in sync with the prod root when changing either one.

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
    prefix = "terraform/dev"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  name        = "misinformation-mitigation-dev"
  cluster_tag = "gke-${local.name}-cluster"
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
  name                    = "${local.name}-vpc-network"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  name          = "${local.name}-subnet"
  ip_cidr_range = "10.12.0.0/16"
  region        = var.region
  network       = google_compute_network.vpc_network.id

  secondary_ip_range {
    range_name    = "pod-ranges"
    ip_cidr_range = "10.120.0.0/16"
  }

  secondary_ip_range {
    range_name    = "services-ranges"
    ip_cidr_range = "10.130.0.0/16"
  }
}

# GKE Cluster
resource "google_container_cluster" "primary" {
  name     = "${local.name}-cluster"
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
    master_ipv4_cidr_block  = "172.16.0.16/28"
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
  name     = "${local.name}-node-pool"
  location = "${var.region}-a"
  cluster  = google_container_cluster.primary.name

  initial_node_count = 1

  autoscaling {
    min_node_count = 1
    max_node_count = 2
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

  lifecycle {
    ignore_changes = [
      node_config[0].resource_labels,
      node_config[0].metadata,
      node_config[0].kubelet_config,
    ]
  }

  node_config {
    preemptible  = false
    machine_type = "e2-medium"

    labels = {
      environment = "dev",
      app         = "misinformation-mitigation"
    }

    service_account = google_service_account.gke_sa.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    tags            = [local.cluster_tag]

    workload_metadata_config {
      mode = "GKE_METADATA"
    }
  }
}

resource "google_compute_firewall" "allow_http_https" {
  name    = "${local.name}-allow-http-https"
  network = google_compute_network.vpc_network.name

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = [local.cluster_tag]
}


# Service Account for GKE
resource "google_service_account" "gke_sa" {
  account_id   = "misinfo-dev-gke-sa"
  display_name = "GKE Service Account (dev)"
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
  name          = "${local.name}-private-ip-address"
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
  name             = "${local.name}-db"
  database_version = "POSTGRES_13"
  region           = var.region

  depends_on = [google_service_networking_connection.private_vpc_connection]

  settings {
    tier    = var.db_tier
    edition = "ENTERPRISE"

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

# Kubernetes Resources (separate cluster, so the namespace and object names match prod)
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
    replicas               = 1
    revision_history_limit = 1

    strategy {
      type = "Recreate"
    }

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
        service_account_name = kubernetes_service_account.workload_identity_sa.metadata[0].name

        container {
          image = var.image_uri
          name  = "misinformation-mitigation-api"

          env {
            name  = "DATABASE_URL"
            value = "postgresql://misinformation_mitigation_user:${var.db_password}@127.0.0.1:5432/misinformation_mitigation_db"
          }

          env {
            name  = "SERPER_API_KEY"
            value = var.serper_api_key
          }

          env {
            name  = "TOGETHER_API_KEY"
            value = var.together_api_key
          }

          env {
            name  = "GOOGLE_SEARCH_API_KEY"
            value = var.google_search_api_key
          }

          env {
            name  = "GOOGLE_SEARCH_ENGINE_ID"
            value = var.google_search_engine_id
          }

          env {
            name  = "AUTH0_CLIENT_SECRET"
            value = var.auth0_client_secret
          }

          env {
            name  = "AUTH0_CLIENT_ID"
            value = var.auth0_client_id
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
            initial_delay_seconds = 120
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

        # Created by hand once per cluster (see docs/dev-environment.md), as in prod
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

  # The pod cannot become ready until the vertex-ai-credentials secret exists
  wait_for_rollout = false
}

resource "kubernetes_service" "misinformation_mitigation_api" {
  metadata {
    name      = "misinformation-mitigation-api"
    namespace = kubernetes_namespace.misinformation_mitigation.metadata[0].name

    annotations = {
      "cloud.google.com/backend-config" = jsonencode({
        "default" = "api-timeout-config"
      })
    }
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
resource "kubernetes_manifest" "api_backend_config" {
  manifest = {
    apiVersion = "cloud.google.com/v1"
    kind       = "BackendConfig"
    metadata = {
      name      = "api-timeout-config"
      namespace = kubernetes_namespace.misinformation_mitigation.metadata[0].name
    }
    spec = {
      timeoutSec = 600 # 600 seconds = 10 minutes
    }
  }
}

resource "google_compute_global_address" "misinformation_mitigation_api_ip" {
  name = "${local.name}-api-ip"
}

resource "google_compute_managed_ssl_certificate" "misinformation_mitigation_cert" {
  name = "${local.name}-cert"
  managed {
    domains = [var.api_hostname]
  }
}

resource "kubernetes_ingress_v1" "misinformation_mitigation_ingress" {
  # GKE appends its auto-provisioned managed certificate to this annotation
  lifecycle {
    ignore_changes = [metadata[0].annotations["ingress.gcp.kubernetes.io/pre-shared-cert"]]
  }

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
      host = var.api_hostname
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
      domains = [var.api_hostname]
    }
  }
}

# The zone is owned by the prod root; dev only adds its own record to it
data "google_dns_managed_zone" "veri_fact_ai" {
  name = "veri-fact-ai-zone"
}

resource "google_dns_record_set" "api_dev" {
  name         = "${var.api_hostname}."
  managed_zone = data.google_dns_managed_zone.veri_fact_ai.name
  type         = "A"
  ttl          = 300

  rrdatas = [google_compute_global_address.misinformation_mitigation_api_ip.address]
}

resource "google_compute_router" "router" {
  name    = "${local.name}-router"
  region  = var.region
  network = google_compute_network.vpc_network.id
}

resource "google_compute_router_nat" "nat" {
  name                               = "${local.name}-nat"
  router                             = google_compute_router.router.name
  region                             = google_compute_router.router.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

resource "google_compute_firewall" "allow_egress" {
  name    = "${local.name}-allow-egress"
  network = google_compute_network.vpc_network.name

  allow {
    protocol = "tcp"
    ports    = ["443"] # HTTPS
  }

  allow {
    protocol = "udp"
    ports    = ["53"] # DNS
  }

  direction          = "EGRESS"
  destination_ranges = ["0.0.0.0/0"] # All destinations
}

# Cluster-local RBAC (the project-level owner grant is managed by the prod root)
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
