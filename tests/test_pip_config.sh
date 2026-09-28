#!/usr/bin/env bash

# Simulate a clean Python 3.12 package installation.
docker run --rm \
    -v "$(pwd):/tmp/gitdata-lib:ro" \
    python:3.12 \
    bash -c 'pip install /tmp/gitdata-lib && python -c "import gitdata.database; print(gitdata.database.__path__)"'
