#!/bin/bash
service mariadb start

mysql_secure_installation <<EOF

y
n
y
y
y
y
EOF

service mariadb stop
