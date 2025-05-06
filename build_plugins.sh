#!/bin/bash

# Exit on error
set -e

# Define plugin folders
PLUGINS=("featurenavigator" "rasterfromvectorfieldloader")

# Create releases directory if it doesn't exist
mkdir -p releases

# Loop over plugin directories and zip each one
for plugin in "${PLUGINS[@]}"; do
    if [ -d "$plugin" ]; then
        zip_name="releases/${plugin}.zip"
        echo "Creating $zip_name..."
        # Create the zip containing the entire folder
        (cd "$(dirname "$plugin")" && zip -r "../$zip_name" "$(basename "$plugin")")
    else
        echo "Directory $plugin does not exist!"
    fi
done

echo "All plugins have been zipped into the 'releases/' folder."
