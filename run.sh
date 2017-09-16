#! /usr/bin/env bash

set -e -o pipefail

cd "$(dirname "$BASH_SOURCE")"

. venv/bin/activate
[ -e settings.sh ] && . settings.sh

options=()

for i in http_listen_address http_listen_port max_episode_count; do
    options=("${options[@]}" "$i=${!i}")
done

python . "${options[@]}"
