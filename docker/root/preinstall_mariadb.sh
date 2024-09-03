#!/bin/bash
apt-get install -y mariadb-server
cp /50-server.cnf /etc/mysql/mariadb.conf.d/50-server.cnf
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

service mariadb stop
