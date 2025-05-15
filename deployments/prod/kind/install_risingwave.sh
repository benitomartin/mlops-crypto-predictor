#!/bin/bash

# Install RisingWave Helm chart repository
helm repo add risingwavelabs https://risingwavelabs.github.io/helm-charts/ --force-update

# Update the Helm chart repository
helm repo update

# Install RisingWave with the values from the risingwave-values.yaml file
helm upgrade --install --create-namespace --wait risingwave risingwavelabs/risingwave --namespace=risingwave -f manifests/risingwave-values.yaml
