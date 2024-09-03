#!/bin/bash
apt-get install -y mariadb-server
cp /50-server.cnf /etc/mysql/mariadb.conf.d/50-server.cnf
