#! /usr/bin/env bash

set -e -o pipefail

cd "$(dirname "$BASH_SOURCE")"

find_command() {
	for i in "$@"; do
		if which "$i" > /dev/null; then
			echo "$i"
			return
		fi
	done
	
	echo "None of these commands found: $@" >&2
	fail
}

# It seems that maintainers can't agree on the name of the virtualenv binary.
VIRTUALENV_COMMAND=$(find_command virtualenv{-3{.{5,4,3,2},},})

# The can't seem to agree for the python binary either.
PYTHON_COMMAND=$(find_command python{3{.{5,4,3,2},},})

rm -rf venv
"$VIRTUALENV_COMMAND" -p "$PYTHON_COMMAND" venv
. venv/bin/activate
pip install google-api-python-client isodate pytz youtube_dl
