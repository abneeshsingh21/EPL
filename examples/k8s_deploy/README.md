# EPL Kubernetes Deployment Example

This example shows how to deploy an EPL web app to Kubernetes.

## Generate the manifests

    epl deploy k8s --image myapp:latest --host myapp.example.com

## What gets generated

    k8s/
    namespace.yaml
    configmap.yaml
    deployment.yaml
    service.yaml
    ingress.yaml
    hpa.yaml

## Apply to your cluster

    kubectl apply -f k8s/

## With TLS enabled

    epl deploy k8s --image myapp:latest --host myapp.example.com --tls
