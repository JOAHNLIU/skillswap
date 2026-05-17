#!/bin/bash
# Run once to initialize migrations
export FLASK_APP=app:create_app
flask db init
flask db migrate -m "initial"
flask db upgrade
echo "Migrations initialized"
