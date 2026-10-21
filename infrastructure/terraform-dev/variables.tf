variable "project_id" {
  description = "The project ID to deploy to"
  default     = "misinformation-mitigation"
}

variable "image_uri" {
  description = "Exact Docker image deployed to Kubernetes"
  type        = string
}

variable "region" {
  description = "The region to deploy to"
  default     = "northamerica-northeast1"
}

variable "api_hostname" {
  description = "Public hostname of the dev API"
  default     = "api-dev.veri-fact.ai"
}

variable "db_tier" {
  description = "Cloud SQL machine tier (prod uses db-custom-1-3840)"
  default     = "db-g1-small"
}

variable "db_password" {
  description = "Database password"
  sensitive   = true
}

variable "user_email" {
  description = "Email of the user to grant permissions"
  default     = "wgarneau@veri-fact.ai"
}

variable "serper_api_key" {
  description = "Serper search API Key"
  sensitive   = true
}

variable "together_api_key" {
  description = "Together AI API Key"
  sensitive   = true
}

variable "google_search_api_key" {
  description = "Google Search API Key"
  sensitive   = true
}

variable "google_search_engine_id" {
  description = "Google Search Engine ID"
}

variable "auth0_client_id" {
  description = "Auth0 Client ID"
}

variable "auth0_client_secret" {
  description = "Auth0 Client Secret"
  sensitive   = true
}
