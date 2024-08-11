#!/bin/bash

# Update package information and install MariaDB server
sudo apt update
sudo apt install -y mariadb-server

sudo sed -i 's/^port\s*=.*/port = 6503/' /etc/mysql/mariadb.conf.d/50-server.cnf

# Secure MariaDB installation (automated with the specified answers)
sudo mysql_secure_installation <<EOF

y
n
y
y
y
y
EOF

# Log in to MariaDB as root using Unix socket authentication and set up the kodi user
sudo mysql -u root <<EOF
CREATE USER 'kodi'@'%' IDENTIFIED BY 'kodi';
GRANT ALL PRIVILEGES ON *.* TO 'kodi'@'%' WITH GRANT OPTION;
FLUSH PRIVILEGES;
EXIT;
EOF

echo "MariaDB installation and kodi user setup complete."