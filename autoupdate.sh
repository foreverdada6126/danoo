#!/bin/bash

# Navigate to the DaNoo project folder on the host (change this if you installed it elsewhere)
cd /root/danoo

# Check for updates from GitHub without overriding local files yet
git fetch origin main >/dev/null 2>&1

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse @{u})

# If the online version is different from the VPS version...
if [ $LOCAL != $REMOTE ]; then
    echo "[$(date)] New GitHub commit detected! Running auto-update..."
    # Execute the update master script!
    ./manage.sh update
fi
