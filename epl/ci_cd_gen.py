"""
CI/CD Pipeline Generator for EPL
Generates CI/CD configuration files for GitLab CI, Jenkins, and CircleCI
"""

import os
import yaml
import json
from typing import Dict, List, Optional
from pathlib import Path


class CICDGenerator:
    """
    CI/CD Pipeline Generator
    Supports GitLab CI, Jenkins, and CircleCI
    """

    SUPPORTED_LANGUAGES = {
       "python": {
    "docker_image": "python:3.9",
    "install_cmd": "pip install -r requirements.txt",
    "test_cmd": "pytest tests/ --junitxml=test-results/results.xml",  # ← Generates XML
    "lint_cmd": "flake8 . && black --check ."
},
        "node": {
            "docker_image": "node:16",
            "install_cmd": "npm install",
            "test_cmd": "npm test",
            "lint_cmd": "npm run lint"
        },
        "java": {
            "docker_image": "maven:3.8-openjdk-11",
            "install_cmd": "mvn clean install -DskipTests",
            "test_cmd": "mvn test",
            "lint_cmd": "mvn checkstyle:check"
        }
    }

    def __init__(self,
                 project_name: str,
                 language: str = "python",
                 output_dir: str = "ci_cd_configs"):
        self.project_name = project_name
        self.language = language.lower()
        self.output_dir = output_dir

        if self.language not in self.SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {language}")

        self.lang_config = self.SUPPORTED_LANGUAGES[self.language]

    def ensure_output_dir(self, subdir: str = ""):
        """Create output directory if it doesn't exist"""
        path = os.path.join(self.output_dir, subdir)
        Path(path).mkdir(parents=True, exist_ok=True)
        return path


#Code for GitLab

    def generate_gitlab_ci(self,
                          stages: Optional[List[str]] = None,
                          custom_commands: Optional[Dict] = None) -> str:
        """Generate GitLab CI/CD configuration"""
        if stages is None:
            stages = ["lint", "build", "test", "deploy"]

        if custom_commands is None:
            custom_commands = {
                "lint": [self.lang_config["lint_cmd"]],
                "build": [self.lang_config["install_cmd"]],
                "test": [self.lang_config["test_cmd"]],
                "deploy": ["echo 'Deploying application...'"]
            }

        config = {
            "image": self.lang_config["docker_image"],
            "stages": stages,
            "variables": {
                "PROJECT_NAME": self.project_name,
            },
            "cache": {
                "paths": [".cache/pip", "venv/", "node_modules/"]
            }
        }

        # Add jobs for each stage
        for stage in stages:
            job_name = f"{stage}_job"
            config[job_name] = {
                "stage": stage,
                "script": custom_commands.get(stage, [f"echo 'Running {stage}'"])
            }

            if stage == "build":
                config[job_name]["artifacts"] = {
                    "paths": ["dist/", "build/"],
                    "expire_in": "1 week"
                }

            if stage == "test":
                config[job_name]["artifacts"] = {
                    "reports": {
                        "junit": "test-results/*.xml"
                    }
                }

        self.ensure_output_dir()
        output_path = os.path.join(self.output_dir, ".gitlab-ci.yml")

        with open(output_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        print(f"✅ GitLab CI configuration generated: {output_path}")
        return output_path


#Code for Jenkins

    def generate_jenkinsfile(self,
                            stages: Optional[List[str]] = None,
                            custom_commands: Optional[Dict] = None) -> str:
        """Generate Jenkinsfile"""
        if stages is None:
            stages = ["Build", "Test", "Deploy"]

        if custom_commands is None:
            custom_commands = {
                "Build": self.lang_config["install_cmd"],
                "Test": self.lang_config["test_cmd"],
                "Deploy": "echo 'Deploying application...'"
            }

        jenkinsfile = f"""pipeline {{
    agent any

    environment {{
        PROJECT_NAME = '{self.project_name}'
    }}

    stages {{
"""

        for stage in stages:
            command = custom_commands.get(stage, f"echo 'Running {stage}'")
            jenkinsfile += f"""        stage('{stage}') {{
            steps {{
                sh '''
                    {command}
                '''
            }}
        }}

"""

        jenkinsfile += """    }

    post {
        always {
            cleanWs()
        }
        success {
            echo '✅ Pipeline completed successfully!'
        }
        failure {
            echo '❌ Pipeline failed!'
        }
    }
}
"""

        self.ensure_output_dir()
        output_path = os.path.join(self.output_dir, "Jenkinsfile")

        with open(output_path, 'w') as f:
            f.write(jenkinsfile)

        print(f"✅ Jenkinsfile generated: {output_path}")
        return output_path


#Code for CircleCI

    def generate_circleci_config(self,
                                custom_commands: Optional[Dict] = None) -> str:
        """Generate CircleCI configuration"""
        executor = self.lang_config["docker_image"]

        if custom_commands is None:
            custom_commands = {
                "install": [self.lang_config["install_cmd"]],
                "test": [self.lang_config["test_cmd"]],
                "deploy": ["echo 'Deploying application...'"]
            }

        config = {
            "version": 2.1,
            "jobs": {
                "build": {
                    "docker": [{"image": executor}],
                    "steps": [
                        "checkout",
                        {
                            "run": {
                                "name": "Install dependencies",
                                "command": "\n".join(custom_commands.get("install", []))
                            }
                        },
                        {
                            "persist_to_workspace": {
                                "root": ".",
                                "paths": ["."]
                            }
                        }
                    ]
                },
                "test": {
                    "docker": [{"image": executor}],
                    "steps": [
                        "checkout",
                        {
                            "attach_workspace": {"at": "."}
                        },
                        {
                            "run": {
                                "name": "Run tests",
                                "command": "\n".join(custom_commands.get("test", []))
                            }
                        }
                    ]
                },
                "deploy": {
                    "docker": [{"image": executor}],
                    "steps": [
                        "checkout",
                        {
                            "run": {
                                "name": "Deploy",
                                "command": "\n".join(custom_commands.get("deploy", []))
                            }
                        }
                    ]
                }
            },
            "workflows": {
                "version": 2,
                "build_test_deploy": {
                    "jobs": [
                        "build",
                        {"test": {"requires": ["build"]}},
                        {
                            "deploy": {
                                "requires": ["test"],
                                "filters": {
                                    "branches": {"only": ["main"]}
                                }
                            }
                        }
                    ]
                }
            }
        }

        circleci_dir = self.ensure_output_dir(".circleci")
        output_path = os.path.join(circleci_dir, "config.yml")

        with open(output_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        print(f"✅ CircleCI configuration generated: {output_path}")
        return output_path

    def generate_all(self, platform: Optional[str] = None):
        """Generate CI/CD configs for all platforms or specific one"""
        print(f"\n🚀 Generating CI/CD configurations for {self.project_name}...\n")

        if platform is None or platform.lower() == "gitlab":
            self.generate_gitlab_ci()

        if platform is None or platform.lower() == "jenkins":
            self.generate_jenkinsfile()

        if platform is None or platform.lower() == "circleci":
            self.generate_circleci_config()

        print(f"\n✨ Done! Check '{self.output_dir}/' directory")


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="CI/CD Pipeline Generator")
    parser.add_argument("--project-name", default="my-project", help="Project name")
    parser.add_argument("--language", choices=["python", "node", "java"],
                       default="python", help="Programming language")
    parser.add_argument("--platform", choices=["gitlab", "jenkins", "circleci", "all"],
                       default="all", help="CI/CD platform")

    args = parser.parse_args()

    generator = CICDGenerator(
        project_name=args.project_name,
        language=args.language
    )

    platform = None if args.platform == "all" else args.platform
    generator.generate_all(platform=platform)


if __name__ == "__main__":
    main()
