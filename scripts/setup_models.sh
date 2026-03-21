#!/bin/bash
# setup_models.sh
# Restores large model files and binaries to their original locations from the .models/ directory.
# If they are not found in .models/, instructions are provided on where to download them.

set -e

echo "Restoring models from .models/..."

if [ -d ".models/echokit/gsv_tts/resources" ]; then
    echo "Found gsv_tts resources. Restoring..."
    mkdir -p tools/echokit/gsv_tts/resources
    cp -r .models/echokit/gsv_tts/resources/* tools/echokit/gsv_tts/resources/
else
    echo "WARNING: .models/echokit/gsv_tts/resources not found."
    echo "Please download the required .pt files and place them in tools/echokit/gsv_tts/resources/"
fi

if [ -d ".models/echokit/libtorch/lib" ]; then
    echo "Found libtorch libraries. Restoring..."
    mkdir -p tools/echokit/libtorch/lib
    cp -r .models/echokit/libtorch/lib/* tools/echokit/libtorch/lib/
else
    echo "WARNING: .models/echokit/libtorch/lib not found."
    echo "Please download the libtorch libraries and place them in tools/echokit/libtorch/lib/"
fi

echo "Model setup complete."
