"""Tests for EPL Kubernetes manifest generator."""

import os
import tempfile

from epl.k8s_gen import (
    generate_all,
    generate_configmap,
    generate_deployment,
    generate_hpa,
    generate_ingress,
    generate_namespace,
    generate_service,
)


def test_namespace_contains_app_name():
    result = generate_namespace('myapp')
    assert 'name: myapp' in result
    assert 'kind: Namespace' in result


def test_namespace_has_epl_label():
    result = generate_namespace('myapp')
    assert 'managed-by: epl' in result


def test_configmap_has_data():
    result = generate_configmap('myapp', {'ENV': 'prod'})
    assert 'kind: ConfigMap' in result
    assert 'ENV: "prod"' in result


def test_configmap_default_env_vars():
    result = generate_configmap('myapp')
    assert 'EPL_ENV' in result
    assert 'production' in result


def test_deployment_image_and_replicas():
    result = generate_deployment('myapp', 'myapp:1.0', replicas=3)
    assert 'image: myapp:1.0' in result
    assert 'replicas: 3' in result


def test_deployment_has_health_probes():
    result = generate_deployment('myapp', 'myapp:latest')
    assert 'livenessProbe' in result
    assert 'readinessProbe' in result


def test_deployment_runs_as_non_root():
    result = generate_deployment('myapp', 'myapp:latest')
    assert 'runAsNonRoot: true' in result


def test_deployment_resource_limits():
    result = generate_deployment('myapp', 'myapp:latest', cpu_limit='1000m', mem_limit='1Gi')
    assert 'cpu: 1000m' in result
    assert 'memory: 1Gi' in result


def test_service_clusterip():
    result = generate_service('myapp', service_type='ClusterIP')
    assert 'type: ClusterIP' in result
    assert 'kind: Service' in result


def test_service_loadbalancer():
    result = generate_service('myapp', service_type='LoadBalancer')
    assert 'type: LoadBalancer' in result


def test_ingress_host():
    result = generate_ingress('myapp', 'myapp.example.com')
    assert 'host: myapp.example.com' in result
    assert 'kind: Ingress' in result


def test_ingress_with_tls():
    result = generate_ingress('myapp', 'myapp.example.com', tls=True, cert_secret='myapp-tls')
    assert 'tls:' in result
    assert 'secretName: myapp-tls' in result


def test_ingress_no_tls_by_default():
    result = generate_ingress('myapp', 'myapp.example.com')
    assert 'secretName' not in result


def test_hpa_replicas():
    result = generate_hpa('myapp', min_replicas=2, max_replicas=10)
    assert 'minReplicas: 2' in result
    assert 'maxReplicas: 10' in result
    assert 'kind: HorizontalPodAutoscaler' in result


def test_hpa_cpu_threshold():
    result = generate_hpa('myapp', cpu_threshold=80)
    assert 'averageUtilization: 80' in result


def test_generate_all_creates_six_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        files = generate_all(
            app_name='testapp',
            image='testapp:latest',
            host='testapp.example.com',
            output_dir=tmpdir,
        )
        assert len(files) == 6
        for f in files:
            assert os.path.isfile(f)
            assert os.path.getsize(f) > 0


def test_generate_all_correct_filenames():
    with tempfile.TemporaryDirectory() as tmpdir:
        files = generate_all('myapp', 'myapp:1.0', 'myapp.com', output_dir=tmpdir)
        names = [os.path.basename(f) for f in files]
        assert 'deployment.yaml' in names
        assert 'service.yaml' in names
        assert 'ingress.yaml' in names
        assert 'hpa.yaml' in names
        assert 'namespace.yaml' in names
        assert 'configmap.yaml' in names
