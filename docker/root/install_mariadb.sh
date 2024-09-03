#!/bin/bash
if [ ! -f "./mariadb_installed" ]; then
  # Update package information and install MariaDB server
  # apt-get update
  # DEBIAN_FRONTEND=noninteractive apt-get install -y mariadb-server
  # sed -i '/^\[mysqld\]/a port = 6503' /etc/mysql/mariadb.conf.d/50-server.cnf
  # sed -i 's/^bind-address\s*=.*/bind-address = 0.0.0.0/' /etc/mysql/mariadb.conf.d/50-server.cnf
  # service mariadb start
  # Secure MariaDB installation (automated with the specified answers)
  mysql_secure_installation <<EOF
  
  y
  n
  y
  y
  y
  y
  EOF
  
  # Log in to MariaDB as root using Unix socket authentication and set up the kodi user
  mysql -u root <<EOF
  CREATE USER 'kodi'@'%' IDENTIFIED BY 'kodi';
  GRANT ALL PRIVILEGES ON *.* TO 'kodi'@'%' WITH GRANT OPTION;
  FLUSH PRIVILEGES;
  EXIT;
  EOF
  # service mariadb stop
  echo "Secure  install and Kodi user setup complete."
  touch ./mariadb_installed
fi
