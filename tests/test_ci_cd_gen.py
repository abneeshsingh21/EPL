"""
Unit tests for CI/CD Generator
"""

import os
import pytest
import yaml
import sys
from pathlib import Path

# Add parent directory to path to import ci_cd_gen
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'epl'))
from ci_cd_gen import CICDGenerator


@pytest.fixture
def generator():
    """Create a CICDGenerator instance for testing"""
    return CICDGenerator(project_name="test-project", language="python")


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up generated files after each test"""
    yield
    # Cleanup code runs after test
    import shutil
    if os.path.exists("ci_cd_configs"):
        shutil.rmtree("ci_cd_configs")


def test_generator_initialization():
    """Test CICDGenerator initialization"""
    generator = CICDGenerator(project_name="my-project", language="python")
    assert generator.project_name == "my-project"
    assert generator.language == "python"
    assert generator.output_dir == "ci_cd_configs"


def test_unsupported_language():
    """Test that unsupported language raises ValueError"""
    with pytest.raises(ValueError):
        CICDGenerator(project_name="test", language="unsupported")


def test_gitlab_ci_generation(generator):
    #Test GitLab CI configuration generation
    output_path = generator.generate_gitlab_ci()

    assert os.path.exists(output_path)
    assert output_path.endswith(".gitlab-ci.yml")

    with open(output_path, 'r') as f:
        config = yaml.safe_load(f)

    assert "stages" in config
    assert "image" in config
    assert config["image"] == "python:3.9"
    assert "lint" in config["stages"]
    assert "build" in config["stages"]
    assert "test" in config["stages"]


def test_jenkinsfile_generation(generator):
   # Test Jenkinsfile generation
    output_path = generator.generate_jenkinsfile()

    assert os.path.exists(output_path)
    assert output_path.endswith("Jenkinsfile")

    with open(output_path, 'r') as f:
        content = f.read()

    assert "pipeline {" in content
    assert "stage('Build')" in content
    assert "stage('Test')" in content
    assert "stage('Deploy')" in content
    assert f"PROJECT_NAME = '{generator.project_name}'" in content


def test_circleci_config_generation(generator):
   #Test CircleCI configuration generation
    output_path = generator.generate_circleci_config()

    assert os.path.exists(output_path)
    assert output_path.endswith("config.yml")

    with open(output_path, 'r') as f:
        config = yaml.safe_load(f)

    assert "version" in config
    assert config["version"] == 2.1
    assert "jobs" in config
    assert "build" in config["jobs"]
    assert "test" in config["jobs"]
    assert "deploy" in config["jobs"]
    assert "workflows" in config


def test_custom_stages_gitlab(generator):
    #Test custom stages configuration for GitLab
    custom_stages = ["lint", "build", "test", "security-scan", "deploy"]
    custom_commands = {
        "lint": ["flake8 ."],
        "security-scan": ["bandit -r ."]
    }

    output_path = generator.generate_gitlab_ci(
        stages=custom_stages,
        custom_commands=custom_commands
    )

    with open(output_path, 'r') as f:
        config = yaml.safe_load(f)

    assert config["stages"] == custom_stages
    assert "security-scan_job" in config


def test_node_language_support():
    #Test Node.js language support
    generator = CICDGenerator(project_name="node-app", language="node")

    assert generator.lang_config["docker_image"] == "node:16"
    assert generator.lang_config["install_cmd"] == "npm install"
    assert generator.lang_config["test_cmd"] == "npm test"


def test_java_language_support():
    #Test Java language support
    generator = CICDGenerator(project_name="java-app", language="java")

    assert generator.lang_config["docker_image"] == "maven:3.8-openjdk-11"
    assert "mvn" in generator.lang_config["install_cmd"]


def test_generate_all(generator):
    #Test generating all CI/CD configurations
    generator.generate_all()

    assert os.path.exists("ci_cd_configs/.gitlab-ci.yml")
    assert os.path.exists("ci_cd_configs/Jenkinsfile")
    assert os.path.exists("ci_cd_configs/.circleci/config.yml")


def test_generate_specific_platform(generator):
    #Test generating config for specific platform only
    generator.generate_all(platform="gitlab")

    assert os.path.exists("ci_cd_configs/.gitlab-ci.yml")
    # Other platform files should not exist
    assert not os.path.exists("ci_cd_configs/Jenkinsfile")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
