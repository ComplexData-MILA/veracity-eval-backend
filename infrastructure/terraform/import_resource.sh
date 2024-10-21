#!/bin/bash

set -e

# Fonction pour importer une ressource de manière sécurisée
import_resource() {
  local resource_type=$1
  local resource_name=$2
  local resource_id=$3

  if terraform state list | grep -q "$resource_type.$resource_name"; then
    echo "Resource $resource_type.$resource_name already in state, skipping import."
  else
    echo "Importing $resource_type.$resource_name..."
    terraform import $resource_type.$resource_name $resource_id
  fi
}

# Importer les ressources
import_resource google_container_cluster primary projects/misinformation-mitigation/locations/northamerica-northeast1-a/clusters/misinformation-mitigation-gke-cluster
import_resource google_container_node_pool primary_nodes projects/misinformation-mitigation/locations/northamerica-northeast1-a/clusters/misinformation-mitigation-gke-cluster/nodePools/misinformation-mitigation-node-pool
import_resource google_compute_network vpc_network projects/misinformation-mitigation/global/networks/misinformation-mitigation-vpc-network
import_resource google_compute_subnetwork subnet projects/misinformation-mitigation/regions/northamerica-northeast1/subnetworks/misinformation-mitigation-subnet
import_resource google_compute_firewall allow_http_https projects/misinformation-mitigation/global/firewalls/allow-http-https
import_resource google_service_account gke_sa projects/misinformation-mitigation/serviceAccounts/misinfo-mitigation-gke-sa@misinformation-mitigation.iam.gserviceaccount.com
import_resource google_sql_database_instance misinformation_mitigation_db misinformation-mitigation-db
import_resource google_sql_database misinformation_mitigation_database projects/misinformation-mitigation/instances/misinformation-mitigation-db/databases/misinformation_mitigation_db
import_resource google_sql_user misinformation_mitigation_user misinformation_mitigation_user//misinformation-mitigation-db
import_resource kubernetes_namespace misinformation_mitigation misinformation-mitigation
import_resource kubernetes_deployment misinformation_mitigation_api misinformation-mitigation/misinformation-mitigation-api
import_resource kubernetes_service misinformation_mitigation_api misinformation-mitigation/misinformation-mitigation-api
import_resource kubernetes_ingress_v1 misinformation_mitigation_ingress misinformation-mitigation/misinformation-mitigation-ingress
import_resource google_dns_managed_zone veri_fact_ai projects/misinformation-mitigation/managedZones/veri-fact-ai-zone
import_resource google_dns_record_set api projects/misinformation-mitigation/managedZones/veri-fact-ai-zone/rrsets/api.veri-fact.ai./A

