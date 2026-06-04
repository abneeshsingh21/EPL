"""
Example: Custom CI/CD configuration for EPL project
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'epl'))

from ci_cd_gen import CICDGenerator  # noqa: E402

generator = CICDGenerator(project_name='EPL-Custom', language='python')

custom_stages = ['lint', 'build', 'test', 'security-scan', 'deploy']

# GitLab uses stage names as keys
gitlab_commands = {
    'lint': ['flake8 .', 'black --check .'],
    'build': ['pip install -r requirements.txt'],
    'test': ['pytest tests/ --junitxml=test-results/results.xml'],
    'security-scan': ['bandit -r .'],
    'deploy': ["echo 'Deploying...'"],
}

# CircleCI uses install/test/deploy keys
circleci_commands = {
    'install': ['pip install -r requirements.txt'],
    'test': ['pytest tests/ --junitxml=test-results/results.xml'],
    'deploy': ["echo 'Deploying...'"],
}

# Jenkins uses exact stage label strings
jenkins_commands = {
    'Lint': 'flake8 . && black --check .',
    'Build': 'pip install -r requirements.txt',
    'Test': 'pytest tests/ --junitxml=test-results/results.xml',
    'Security Scan': 'bandit -r .',
    'Deploy': "echo 'Deploying...'",
}

generator.generate_gitlab_ci(stages=custom_stages, custom_commands=gitlab_commands)
generator.generate_jenkinsfile(
    stages=['Lint', 'Build', 'Test', 'Security Scan', 'Deploy'],
    custom_commands=jenkins_commands,
)
generator.generate_circleci_config(custom_commands=circleci_commands)

print('✅ Custom CI/CD configs generated!')
