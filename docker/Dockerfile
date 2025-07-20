FROM ubuntu AS builder

# RUN apt update && apt install golang libfuse
RUN set -eux; \
	apt-get update; \
	apt-get install -y --no-install-recommends \
		g++ \
        	golang \
        	libfuse-dev \
		gcc \
		libc6-dev \
		make \
		pkg-config



RUN apt-get update && apt-get install git -y

ADD https://api.github.com/repos/philamp/rclone_jelly/git/refs/heads/master rclone_jelly_version.json

RUN rm -rf /go/src/github.com/rclone/rclone/

RUN mkdir -p /go/src/github.com/rclone/rclone/

WORKDIR /go/src/github.com/rclone/rclone/

RUN git clone -b master https://github.com/philamp/rclone_jelly.git --single-branch .

RUN CGO_ENABLED=0 make
RUN ./rclone version

# ---RCLONE EXPORT END----

FROM jellyfin/jellyfin:10.10.7

# Docker build runtime vars (ARG) and env vars
ENV v_rar2fs=${RAR2FS_VERSION:-1.29.6}
ENV v_unrar=${UNRAR_VERSION:-6.1.3}
ENV S6_OVERLAY_VERSION="3.1.5.0"
ENV S6_OVERLAY_ARCH="x86_64"

# apt get stuff (add jmalloc to improve Jellyfin memory usage)
RUN apt-get update && \
    apt-get -y install xz-utils libjemalloc2 

# ---RCLONE IMPORT----
COPY --from=builder /go/src/github.com/rclone/rclone/rclone /usr/bin/rclone-linux

# --- Python ---
# python3-venv and co. is fix of https://github.com/philamp/jellygrail/issues/2
RUN apt-get -y install python3 python3-pip python3-venv
COPY root/requirements.txt /requirements.txt
RUN python3 -m venv /opt/venv
RUN /opt/venv/bin/pip install --upgrade pip
RUN /opt/venv/bin/pip install -r /requirements.txt
ENV PATH="/opt/venv/bin:$PATH"

# RAR2FS build
RUN WORKDIR=`mktemp -d` && \
    cd $WORKDIR && \
    # Get deps
    apt-get update && \
    apt-get -y install \
    fuse \
    g++ \
    libfuse-dev \
    make \
    wget && \
    # Get, make and install unrar
    wget http://www.rarlab.com/rar/unrarsrc-${v_unrar}.tar.gz && \
    tar zxvf unrarsrc-${v_unrar}.tar.gz && \
    cd unrar && \
    make && \
    make install && \
    make lib && \
    make install-lib && \
    cd .. && \
    # Get, make and install rar2fs
    wget https://github.com/hasse69/rar2fs/releases/download/v${v_rar2fs}/rar2fs-${v_rar2fs}.tar.gz -O rar2fs-${v_rar2fs}.tar.gz && \
    tar zxvf rar2fs-${v_rar2fs}.tar.gz && \
    cd rar2fs-${v_rar2fs} && \
    ./configure --with-unrar=../unrar --with-unrar-lib=/usr/lib/ && \
    make && \
    make install && \
    # Cleanup
    rm -rf $WORKDIR

# add s6 overlay
RUN cd /tmp && \
    wget https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz && \
    tar -C / -Jxpf /tmp/s6-overlay-noarch.tar.xz && \
    wget https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${S6_OVERLAY_ARCH}.tar.xz && \
    tar -C / -Jxpf /tmp/s6-overlay-${S6_OVERLAY_ARCH}.tar.xz

# set JG folders and permissions
RUN chmod ugo+rx /usr/bin/rclone-linux && \
    mkdir -p /Video_Library && \
    mkdir -p /Cache_Check_Video_Library && \
    mkdir -p /Kodi_Video_Library && \
    mkdir -p /mounts/kodi/software && \
    mkdir -p /mounts/kodi/backups

# kodi addons script copy into container
COPY root/kodi_addons.sh /kodi_addons.sh
RUN chmod +x /kodi_addons.sh

# nginx
RUN apt-get -y install nginx nginx-extras unzip
    
# COPY webdav.conf /etc/nginx/conf.d/default.conf -- now done in init
RUN rm /etc/nginx/sites-enabled/*

# --- BINDFS
# Get deps for bindfs build
RUN apt-get update && \
    apt-get -y install \
    build-essential \
    pkg-config \
    git \
    autoconf \
    libtool \
    libfuse3-dev \
    libsqlite3-dev \
    cmake

ADD https://api.github.com/repos/philamp/bindfs_jelly/git/refs/heads/master bindfs_jelly_version.json

# bindfs build 
RUN WORKDIR=`mktemp -d` && \
    cd $WORKDIR && \
    git clone -b master https://github.com/philamp/bindfs_jelly.git --single-branch . && \
    mkdir build && \
    cd build && \
    cmake .. && \
    make clean all install && \
    rm -rf $WORKDIR

# Mariadb package install
RUN env DEBIAN_FRONTEND=noninteractive apt-get install -y mariadb-server netcat-openbsd
    
# copy the rest
COPY root/ /
RUN chmod u+x /init
RUN chmod -R +x /etc/s6-overlay/s6-rc.d

# ffprobew build
RUN cd /usr/local/bin/ffprobe_wrapper && \
    gcc -o ffprobew ffprobew.c

# ffprobe becomes ffprober
RUN mv /usr/lib/jellyfin-ffmpeg/ffprobe /usr/lib/jellyfin-ffmpeg/ffprober
# ffprobew becomes ffprobe via cp
RUN cp /usr/local/bin/ffprobe_wrapper/ffprobew /usr/lib/jellyfin-ffmpeg/ffprobe

# ffprober and ffprobe(w) are available system wide
RUN cd /usr/local/bin && \
    ln -s /usr/lib/jellyfin-ffmpeg/ffprober ffprober && \
    ln -s /usr/lib/jellyfin-ffmpeg/ffprobe ffprobe

# Reduce image size
# not in dev !! RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# mysql
ENV MYSQL_DIR="/jellygrail/data/mariadb"
ENV DATADIR=$MYSQL_DIR/databases

# expose nginx
EXPOSE 8085

# expose ssh for development
EXPOSE 23

# expose 6502 jelly_update script
EXPOSE 6502

# expose mariadbd
EXPOSE 6503

# overwrite run jellyfin main original process as CMD instead of entrypoint
ENTRYPOINT ["/init"]
CMD ["python3", "/usr/local/bin/grail_jelly/main.py"]

# CMD ["/bin/bash"]
