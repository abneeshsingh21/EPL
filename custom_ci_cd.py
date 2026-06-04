from epl.ci_cd_gen import CICDGenerator

# Initialize generator
generator = CICDGenerator(project_name="EPL-Custom", language="python")

# Define custom stages
custom_stages = ["lint", "build", "test", "security-scan", "deploy"]

# Define custom commands for each stage
custom_commands = {
    "lint": ["flake8 .", "black --check ."],
    "build": ["pip install -r requirements.txt"],
    "test": ["pytest tests/ -v --cov"],
    "security-scan": ["bandit -r .", "safety check"],
    "deploy": ["./deploy.sh"]
}

# Generate with custom configuration
generator.generate_gitlab_ci(stages=custom_stages, custom_commands=custom_commands)
generator.generate_jenkinsfile(stages=["Lint", "Build", "Test", "Security Scan", "Deploy"], custom_commands=custom_commands)
generator.generate_circleci_config(custom_commands=custom_commands)

print("✅ Custom CI/CD configs generated!")
