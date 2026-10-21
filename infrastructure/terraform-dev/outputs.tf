output "kubernetes_cluster_name" {
  value       = google_container_cluster.primary.name
  description = "GKE Cluster Name"
}

output "database_connection_name" {
  value = google_sql_database_instance.misinformation_mitigation_db.connection_name
}

output "api_ip_address" {
  value       = google_compute_global_address.misinformation_mitigation_api_ip.address
  description = "The IP address for the dev API"
}
