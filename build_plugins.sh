#!/bin/bash

set -e

rm -rf ./releases

# Define plugin folders
PLUGINS=("featurenavigator" "rasterfromvectorfieldloader")

# Create releases directory
RELEASE_DIR="releases"
mkdir -p "$RELEASE_DIR"

# Zip each plugin directory
for plugin in "${PLUGINS[@]}"; do
    if [ -d "$plugin" ]; then
        zip_path="${RELEASE_DIR}/${plugin}.zip"
        echo "Creating $zip_path..."
        zip -r "$zip_path" "$plugin"
    else
        echo "Directory $plugin does not exist!"
    fi
done

echo "✅ All plugins zipped into '$RELEASE_DIR/'."
