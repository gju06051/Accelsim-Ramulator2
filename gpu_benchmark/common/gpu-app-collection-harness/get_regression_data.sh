#!/bin/bash
export BASH_ROOT="$( cd "$( dirname "$BASH_SOURCE" )" && pwd )"
DATA_SUBDIR="/data_dirs/"
DATA_ROOT=$BASH_ROOT$DATA_SUBDIR

if [ ! -d $DATA_ROOT ]; then
    mkdir -p "$DATA_ROOT"
fi

echo "Rodinia 2.0-ft data download is disabled in this local tree."
echo "Use gpu_benchmark/scripts/fetch_gpu_app_collection_data.sh for the shared dataset bundle."
