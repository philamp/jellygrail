#!/bin/bash
if [ ! -d /var/lib/mysql/mysql ]; then
  echo "Initializing MariaDB data directory..."
  mariadb-install-db --user=root --datadir=/var/lib/mysql
fi
