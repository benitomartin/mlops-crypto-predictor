#!/bin/bash

# Install Grafana Helm chart repository
helm repo add grafana https://grafana.github.io/helm-charts

# Update the Helm chart repository
helm upgrade --install --create-namespace --wait grafana grafana/grafana --namespace=monitoring --values manifests/grafana-values.yaml
