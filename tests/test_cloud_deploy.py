"""Tests for EPL Cloud Provider Deploy Commands Generator."""

import os
import tempfile

from epl.cloud_deploy import (
    generate_aws_all,
    generate_azure_all,
    generate_azure_containerapp,
    generate_azure_deploy_script,
    generate_cloudbuild_yaml,
    generate_cloudrun_deploy_script,
    generate_ecr_push_script,
    generate_ecs_service,
    generate_ecs_task_definition,
    generate_gcp_all,
)

# ── AWS Tests ──────────────────────────────────────────────


def test_ecr_push_script_contains_app_name():
    result = generate_ecr_push_script('myapp', 'myapp:latest')
    assert 'myapp' in result
    assert 'docker build' in result
    assert 'docker push' in result


def test_ecr_push_script_region():
    result = generate_ecr_push_script('myapp', 'myapp:latest', region='eu-west-1')
    assert 'eu-west-1' in result


def test_ecs_task_definition_structure():
    result = generate_ecs_task_definition('myapp', 'myapp:latest')
    import json

    data = json.loads(result)
    assert data['family'] == 'myapp'
    assert data['requiresCompatibilities'] == ['FARGATE']
    assert len(data['containerDefinitions']) == 1


def test_ecs_task_definition_port():
    result = generate_ecs_task_definition('myapp', 'myapp:latest', port=9000)
    import json

    data = json.loads(result)
    assert data['containerDefinitions'][0]['portMappings'][0]['containerPort'] == 9000


def test_ecs_task_definition_has_health_check():
    result = generate_ecs_task_definition('myapp', 'myapp:latest')
    import json

    data = json.loads(result)
    assert 'healthCheck' in data['containerDefinitions'][0]


def test_ecs_service_structure():
    result = generate_ecs_service('myapp')
    import json

    data = json.loads(result)
    assert data['launchType'] == 'FARGATE'
    assert data['serviceName'] == 'myapp-service'


def test_aws_all_creates_three_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        files = generate_aws_all('myapp', 'myapp:latest', output_dir=tmpdir)
        assert len(files) == 3
        names = [os.path.basename(f) for f in files]
        assert 'ecr-push.sh' in names
        assert 'task-definition.json' in names
        assert 'ecs-service.json' in names


# ── GCP Tests ──────────────────────────────────────────────


def test_cloudrun_script_contains_app_name():
    result = generate_cloudrun_deploy_script('myapp', 'myapp:latest')
    assert 'myapp' in result
    assert 'gcloud run deploy' in result


def test_cloudrun_script_region():
    result = generate_cloudrun_deploy_script('myapp', 'myapp:latest', region='europe-west1')
    assert 'europe-west1' in result


def test_cloudrun_script_port():
    result = generate_cloudrun_deploy_script('myapp', 'myapp:latest', port=9000)
    assert '9000' in result


def test_cloudbuild_yaml_structure():
    result = generate_cloudbuild_yaml('myapp', 'my-project')
    assert 'cloud-builders/gcloud' in result
    assert 'myapp' in result
    assert 'my-project' in result


def test_gcp_all_creates_two_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        files = generate_gcp_all('myapp', 'myapp:latest', output_dir=tmpdir)
        assert len(files) == 2
        names = [os.path.basename(f) for f in files]
        assert 'cloudrun-deploy.sh' in names
        assert 'cloudbuild.yaml' in names


# ── Azure Tests ────────────────────────────────────────────


def test_azure_containerapp_contains_app_name():
    result = generate_azure_containerapp('myapp', 'myapp:latest')
    assert 'myapp' in result
    assert 'containerPort' not in result
    assert 'targetPort' in result


def test_azure_containerapp_region():
    result = generate_azure_containerapp('myapp', 'myapp:latest', region='westeurope')
    assert 'westeurope' in result


def test_azure_containerapp_scaling():
    result = generate_azure_containerapp('myapp', 'myapp:latest')
    assert 'minReplicas' in result
    assert 'maxReplicas' in result


def test_azure_deploy_script_contains_az_commands():
    result = generate_azure_deploy_script('myapp', 'myapp:latest')
    assert 'az group create' in result
    assert 'az containerapp create' in result
    assert 'az containerapp env create' in result


def test_azure_all_creates_two_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        files = generate_azure_all('myapp', 'myapp:latest', output_dir=tmpdir)
        assert len(files) == 2
        names = [os.path.basename(f) for f in files]
        assert 'containerapp.yaml' in names
        assert 'azure-deploy.sh' in names
