#!/bin/bash

# Update package information and install MariaDB server
apt-get update
apt-get install -y mariadb-server
sed -i 's/^port\s*=.*/port = 6503/' /etc/mysql/mariadb.conf.d/50-server.cnf
service mariadb start
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
service mariadb stop
echo "MariaDB installation and kodi user setup complete."
