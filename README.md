# K-12 Data Reliability Hub

## Project purpose

K-12 Data Reliability Hub is an OAISD-inspired, local-first portfolio project demonstrating reliable, privacy-aware K-12 data infrastructure.

## Current development status

The repository currently provides the typed Python package foundation, environment-based configuration, structured logging, and quality tooling. Data pipelines and infrastructure are not implemented yet.

## Basic setup

Python 3.9 or newer and GNU Make are required.

```sh
make install
cp .env.example .env
```

The project uses safe local defaults, so copying the example environment file is optional for local development.

## Available quality commands

```sh
make format
make lint
make typecheck
make test
make verify
```

## Synthetic-data disclaimer

This project must never use real student information. Any student-level or operational examples are deterministic synthetic data and must be clearly labeled and kept separate from clearly sourced public aggregate datasets.
