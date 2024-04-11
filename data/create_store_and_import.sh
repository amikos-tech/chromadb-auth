#!/bin/sh
set -e
STORE_FILE=/data/store.json
if test -f "$STORE_FILE"; then
    echo "Store already exists, skipping creation and import."
    exit 0
fi

fga store create --model /data/models/model-article-p4.fga --name chroma-auth > $STORE_FILE
export FGA_STORE_ID=$(jq -r .store.id $STORE_FILE)
export FGA_MODEL_ID=$(jq -r .model.authorization_model_id $STORE_FILE)

fga tuple write --file /data/data/initial-data.json
