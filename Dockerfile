# ─── EPL Docker Image ─────────────────────────────────
# Build:  docker build -t epl .
# Run:    docker run epl run hello.epl
# REPL:   docker run -it epl repl
# Serve:  docker run -p 3000:3000 epl serve app.epl

FROM python:3.12-slim

LABEL maintainer="EPL Team"
LABEL description="EPL — English Programming Language"
LABEL version="7.0.0"

# Install EPL
WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -e . 2>/dev/null || \
    pip install --no-cache-dir . 2>/dev/null || \
    echo "Installing from source"

# Verify installation
RUN python -c "import epl; print(f'EPL {epl.__version__} installed')"

# Default working directory for user code
WORKDIR /code

# Copy example files for quick testing
COPY examples/ /examples/

# Expose web server port
EXPOSE 3000

# Default: show help
ENTRYPOINT ["epl"]
CMD ["--help"]
