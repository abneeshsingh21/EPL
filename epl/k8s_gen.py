"""EPL Kubernetes Manifest Generator (v1.0)

Generates Kubernetes manifests from EPL app config.
Usage:
    epl deploy k8s --image myapp:1.0 --host myapp.example.com
"""

import os
import re
import textwrap


# ═══════════════════════════════════════════════════════════
# Input Validation — prevent YAML/shell injection
# ═══════════════════════════════════════════════════════════

_SAFE_NAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9._-]{0,62}$')
_SAFE_IMAGE_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._/:@-]{0,255}$')
_SAFE_HOST_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9.*-]{0,253}$')
_VALID_SERVICE_TYPES = ('ClusterIP', 'NodePort', 'LoadBalancer', 'ExternalName')


def _validate_name(value: str, field: str) -> str:
    if not value or not _SAFE_NAME_RE.match(value):
        raise ValueError(
            f'Invalid {field}: must start with a letter and contain only '
            f'[a-zA-Z0-9._-], got: {value!r}'
        )
    return value


def _validate_image(value: str) -> str:
    if not value or not _SAFE_IMAGE_RE.match(value):
        raise ValueError(f'Invalid image reference: must match [a-zA-Z0-9._/:@-]+, got: {value!r}')
    return value


def _validate_host(value: str) -> str:
    if not value or not _SAFE_HOST_RE.match(value):
        raise ValueError(f'Invalid hostname: must match [a-zA-Z0-9.*-]+, got: {value!r}')
    return value


def _validate_port(value: int) -> int:
    if not isinstance(value, int) or value < 1 or value > 65535:
        raise ValueError(f'Invalid port: must be 1-65535, got: {value!r}')
    return value


def _validate_service_type(value: str) -> str:
    if value not in _VALID_SERVICE_TYPES:
        raise ValueError(
            f'Invalid service type: must be one of {_VALID_SERVICE_TYPES}, got: {value!r}'
        )
    return value


def generate_namespace(app_name: str) -> str:
    """Generate a Kubernetes Namespace manifest."""
    app_name = _validate_name(app_name, 'app_name')
    return textwrap.dedent(f"""\
        apiVersion: v1
        kind: Namespace
        metadata:
          name: {app_name}
          labels:
            app: {app_name}
            managed-by: epl
    """)


def generate_configmap(app_name: str, env_vars: dict = None) -> str:
    """Generate a ConfigMap for non-secret environment variables."""
    app_name = _validate_name(app_name, 'app_name')
    if env_vars is None:
        env_vars = {'EPL_ENV': 'production', 'EPL_LOG_LEVEL': 'info'}
    data_lines = '\n'.join(f'  {k}: "{v}"' for k, v in env_vars.items())
    return textwrap.dedent(f"""\
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: {app_name}-config
          namespace: {app_name}
          labels:
            app: {app_name}
        data:
        {data_lines}
    """)


def generate_deployment(
    app_name: str,
    image: str,
    port: int = 8000,
    replicas: int = 2,
    cpu_request: str = '100m',
    cpu_limit: str = '500m',
    mem_request: str = '128Mi',
    mem_limit: str = '512Mi',
) -> str:
    """Generate a Deployment manifest."""
    app_name = _validate_name(app_name, 'app_name')
    image = _validate_image(image)
    port = _validate_port(port)
    return textwrap.dedent(f"""\
        apiVersion: apps/v1
        kind: Deployment
        metadata:
          name: {app_name}
          namespace: {app_name}
        spec:
          replicas: {replicas}
          selector:
            matchLabels:
              app: {app_name}
          template:
            metadata:
              labels:
                app: {app_name}
            spec:
              securityContext:
                runAsNonRoot: true
                runAsUser: 1000
              containers:
                - name: {app_name}
                  image: {image}
                  ports:
                    - containerPort: {port}
                  resources:
                    requests:
                      cpu: {cpu_request}
                      memory: {mem_request}
                    limits:
                      cpu: {cpu_limit}
                      memory: {mem_limit}
                  livenessProbe:
                    httpGet:
                      path: /_health
                      port: {port}
                    initialDelaySeconds: 15
                    periodSeconds: 20
                  readinessProbe:
                    httpGet:
                      path: /_health
                      port: {port}
                    initialDelaySeconds: 5
                    periodSeconds: 10
    """)


def generate_service(app_name: str, port: int = 8000, service_type: str = 'ClusterIP') -> str:
    """Generate a Service manifest."""
    app_name = _validate_name(app_name, 'app_name')
    port = _validate_port(port)
    service_type = _validate_service_type(service_type)
    return textwrap.dedent(f"""\
        apiVersion: v1
        kind: Service
        metadata:
          name: {app_name}-svc
          namespace: {app_name}
        spec:
          type: {service_type}
          selector:
            app: {app_name}
          ports:
            - protocol: TCP
              port: 80
              targetPort: {port}
    """)


def generate_ingress(app_name: str, host: str, tls: bool = False, cert_secret: str = None) -> str:
    """Generate an Ingress manifest."""
    app_name = _validate_name(app_name, 'app_name')
    host = _validate_host(host)
    if cert_secret:
        cert_secret = _validate_name(cert_secret, 'cert_secret')
    tls_block = ''
    if tls:
        secret = cert_secret or f'{app_name}-tls'
        tls_block = f'  tls:\n    - hosts:\n        - {host}\n      secretName: {secret}\n'
    return textwrap.dedent(f"""\
        apiVersion: networking.k8s.io/v1
        kind: Ingress
        metadata:
          name: {app_name}-ingress
          namespace: {app_name}
          annotations:
            nginx.ingress.kubernetes.io/rewrite-target: /
        spec:
        {tls_block}  rules:
            - host: {host}
              http:
                paths:
                  - path: /
                    pathType: Prefix
                    backend:
                      service:
                        name: {app_name}-svc
                        port:
                          number: 80
    """)


def generate_hpa(
    app_name: str, min_replicas: int = 2, max_replicas: int = 10, cpu_threshold: int = 70
) -> str:
    """Generate a HorizontalPodAutoscaler manifest."""
    app_name = _validate_name(app_name, 'app_name')
    return textwrap.dedent(f"""\
        apiVersion: autoscaling/v2
        kind: HorizontalPodAutoscaler
        metadata:
          name: {app_name}-hpa
          namespace: {app_name}
        spec:
          scaleTargetRef:
            apiVersion: apps/v1
            kind: Deployment
            name: {app_name}
          minReplicas: {min_replicas}
          maxReplicas: {max_replicas}
          metrics:
            - type: Resource
              resource:
                name: cpu
                target:
                  type: Utilization
                  averageUtilization: {cpu_threshold}
    """)


def generate_all(
    app_name: str,
    image: str,
    host: str,
    output_dir: str = './k8s',
    port: int = 8000,
    replicas: int = 2,
    tls: bool = False,
    cert_secret: str = None,
    service_type: str = 'ClusterIP',
    env_vars: dict = None,
    min_replicas: int = 2,
    max_replicas: int = 10,
) -> list:
    """Generate all 6 manifests and write them to output_dir."""
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    manifests = {
        'namespace.yaml': generate_namespace(app_name),
        'configmap.yaml': generate_configmap(app_name, env_vars),
        'deployment.yaml': generate_deployment(app_name, image, port, replicas),
        'service.yaml': generate_service(app_name, port, service_type),
        'ingress.yaml': generate_ingress(app_name, host, tls, cert_secret),
        'hpa.yaml': generate_hpa(app_name, min_replicas, max_replicas),
    }

    written = []
    for filename, content in manifests.items():
        path = os.path.join(output_dir, filename)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        written.append(path)

    return written
