FROM python:3.12-slim

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /src

COPY README.md requirements.txt setup.py ./
COPY gitdata ./gitdata
COPY tests/requirements.txt ./tests/requirements.txt

RUN python -m pip install --no-cache-dir '.[oracle]' -r tests/requirements.txt

COPY examples ./examples
COPY tests ./tests
