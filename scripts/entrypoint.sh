#!/bin/bash

############################################################################
# Container Entrypoint script
############################################################################

if [[ "$PRINT_ENV_ON_LOAD" = true || "$PRINT_ENV_ON_LOAD" = True ]]; then
  echo "=================================================="
  printenv
  echo "=================================================="
fi

if [[ "$WAIT_FOR_DB" = true || "$WAIT_FOR_DB" = True ]]; then
  dockerize \
    -wait tcp://$DB_HOST:$DB_PORT \
    -timeout 300s
fi

############################################################################
# Start App
############################################################################

case "$1" in
  chill)
    echo ">>> Hello World!"
    while true; do sleep 18000; done
    ;;
  *)
    echo "Running: $@"
    exec "$@"
    ;;
esac

# This line should never be reached when exec is used
# If we get here, it means exec failed
echo "ERROR: Command failed to execute properly"
exit 1
