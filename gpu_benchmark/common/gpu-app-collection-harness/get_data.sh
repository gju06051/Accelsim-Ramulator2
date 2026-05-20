#!/bin/bash
set -e

export BASH_ROOT="$( cd "$( dirname "$BASH_SOURCE" )" && pwd )"
DATA_SUBDIR="/data_dirs/"
DATA_ROOT=$BASH_ROOT$DATA_SUBDIR
DATA_PATH="${DATA_ROOT%/}"
DATA_URL="https://engineering.purdue.edu/tgrogers/gpgpu-sim/benchmark_data/all.gpgpu-sim-app-data.tgz"

has_data() {
    [ -d "$DATA_ROOT" ] && find "$DATA_ROOT" -mindepth 1 -print -quit | grep -q .
}

if ! has_data; then
    mkdir -p "$DATA_ROOT"

    if [ -L "$DATA_PATH" ]; then
        EXTRACT_ROOT="$(dirname "$(readlink -f "$DATA_PATH")")"
    else
        EXTRACT_ROOT="$BASH_ROOT"
    fi

    TAR_DIR="$EXTRACT_ROOT"
    TARBALL="$TAR_DIR/all.gpgpu-sim-app-data.tgz"
    OLD_TARBALL="$BASH_ROOT/all.gpgpu-sim-app-data.tgz"

    if [ -f "$OLD_TARBALL" ] && [ "$OLD_TARBALL" != "$TARBALL" ] && [ ! -f "$TARBALL" ]; then
        mv "$OLD_TARBALL" "$TARBALL"
    fi

    wget -c -O "$TARBALL" "$DATA_URL"
    tar xzvf "$TARBALL" -C "$EXTRACT_ROOT"
    rm "$TARBALL"
fi
