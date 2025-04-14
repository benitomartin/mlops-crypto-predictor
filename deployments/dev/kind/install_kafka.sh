#!/bin/bash

# Strimzi creates the kube-system pods
# Then it creates the kafka pods using the kafka-e11b.yaml file
kubectl create namespace kafka
kubectl create -f 'https://strimzi.io/install/latest?namespace=kafka' -n kafka
kubectl apply -f manifests/kafka-e11b.yaml
