"""
Unit tests for CI/CD Generator
"""

import os
import sys

import pytest
import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'epl')))

from ci_cd_gen import CICDGenerator  # noqa: E402


@pytest.fixture
def generator(tmp_path):
    """Create a CICDGenerator instance for testing"""
    return CICDGenerator(
        project_name='test-project',
        language='python',
        output_dir=str(tmp_path / 'ci_cd_configs'),
    )


def test_generator_initialization():
    """Test CICDGenerator initialization"""
    gen = CICDGenerator(project_name='my-project', language='python')
    assert gen.project_name == 'my-project'
    assert gen.language == 'python'
    assert gen.output_dir == 'ci_cd_configs'


def test_unsupported_language():
    """Test that unsupported language raises ValueError"""
    with pytest.raises(ValueError):
        CICDGenerator(project_name='test', language='unsupported')


def test_unsupported_platform(generator):
    """Test that unsupported platform raises ValueError"""
    with pytest.raises(ValueError):
        generator.generate_all(platform='unsupported')


def test_gitlab_ci_generation(generator):
    """Test GitLab CI configuration generation"""
    output_path = generator.generate_gitlab_ci()

    assert os.path.exists(output_path)
    assert output_path.endswith('.gitlab-ci.yml')

    with open(output_path) as f:
        config = yaml.safe_load(f)

    assert 'stages' in config
    assert 'image' in config
    assert config['image'] == 'python:3.9'
    assert 'lint' in config['stages']
    assert 'build' in config['stages']
    assert 'test' in config['stages']


def test_jenkinsfile_generation(generator):
    """Test Jenkinsfile generation"""
    output_path = generator.generate_jenkinsfile()

    assert os.path.exists(output_path)
    assert output_path.endswith('Jenkinsfile')

    with open(output_path) as f:
        content = f.read()

    assert 'pipeline {' in content
    assert "stage('Build')" in content
    assert "stage('Test')" in content
    assert "stage('Deploy')" in content
    assert f"PROJECT_NAME = '{generator.project_name}'" in content


def test_circleci_config_generation(generator):
    """Test CircleCI configuration generation"""
    output_path = generator.generate_circleci_config()

    assert os.path.exists(output_path)
    assert output_path.endswith('config.yml')

    with open(output_path) as f:
        config = yaml.safe_load(f)

    assert 'version' in config
    assert config['version'] == 2.1
    assert 'jobs' in config
    assert 'build' in config['jobs']
    assert 'test' in config['jobs']
    assert 'deploy' in config['jobs']
    assert 'workflows' in config


def test_custom_stages_gitlab(generator):
    """Test custom stages configuration for GitLab"""
    custom_stages = ['lint', 'build', 'test', 'security-scan', 'deploy']
    custom_commands = {
        'lint': ['flake8 .'],
        'security-scan': ['bandit -r .'],
    }

    output_path = generator.generate_gitlab_ci(
        stages=custom_stages,
        custom_commands=custom_commands,
    )

    with open(output_path) as f:
        config = yaml.safe_load(f)

    assert config['stages'] == custom_stages
    assert 'security-scan_job' in config


def test_node_language_support():
    """Test Node.js language support"""
    gen = CICDGenerator(project_name='node-app', language='node')
    assert gen.lang_config['docker_image'] == 'node:16'
    assert gen.lang_config['install_cmd'] == 'npm install'
    assert gen.lang_config['test_cmd'] == 'npm test'


def test_java_language_support():
    """Test Java language support"""
    gen = CICDGenerator(project_name='java-app', language='java')
    assert gen.lang_config['docker_image'] == 'maven:3.8-openjdk-11'
    assert 'mvn' in gen.lang_config['install_cmd']


def test_generate_all(generator):
    """Test generating all CI/CD configurations"""
    generator.generate_all()

    output_dir = generator.output_dir
    assert os.path.exists(os.path.join(output_dir, '.gitlab-ci.yml'))
    assert os.path.exists(os.path.join(output_dir, 'Jenkinsfile'))
    assert os.path.exists(os.path.join(output_dir, '.circleci', 'config.yml'))


def test_generate_specific_platform(generator):
    """Test generating config for specific platform only"""
    generator.generate_all(platform='gitlab')

    output_dir = generator.output_dir
    assert os.path.exists(os.path.join(output_dir, '.gitlab-ci.yml'))
    assert not os.path.exists(os.path.join(output_dir, 'Jenkinsfile'))
    assert not os.path.exists(os.path.join(output_dir, '.circleci', 'config.yml'))


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
