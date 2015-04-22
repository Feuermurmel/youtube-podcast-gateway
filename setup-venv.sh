#! /usr/bin/env bash

set -e -o pipefail

cd "$(dirname "$BASH_SOURCE")"

rm -rf venv
virtualenv-3.4 venv
. venv/bin/activate
pip install google-api-python-client isodate pytz
