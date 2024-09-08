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

RUN git clone https://github.com/philamp/rclone_jelly.git .

RUN CGO_ENABLED=0 make
RUN ./rclone version

# ---RCLONE EXPORT END----

FROM jellyfin/jellyfin

# Docker build runtime vars (ARG) and env vars
ENV v_rar2fs=${RAR2FS_VERSION:-1.29.6}
ENV v_unrar=${UNRAR_VERSION:-6.0.7}
ENV S6_OVERLAY_VERSION="3.1.5.0"
ENV S6_OVERLAY_ARCH="x86_64"

# ---RCLONE IMPORT----
COPY --from=builder /go/src/github.com/rclone/rclone/rclone /usr/bin/rclone-linux

# apt get stuff
RUN apt-get update && \
    apt-get -y install xz-utils

# python3-venv is fix of https://github.com/philamp/jellygrail/issues/2 (+l123)
RUN apt-get -y install python3 python3-pip python3-venv

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



# add rclone fork
# RUN cd /usr/bin && \
    # wget https://github.com/itsToggle/rclone_RD/releases/download/v1.58.1-rd.2.2/rclone-linux

# set folders and permissions
RUN chmod ugo+rx /usr/bin/rclone-linux && \
    mkdir -p /Video_Library && \
    mkdir -p /Cache_Check_Video_Library && \
    mkdir -p /mounts/kodi/software && \
    mkdir -p /mounts/kodi/backups
    # mkdir -p /root/.config/rclone
    # mkdir -p /volumeG/rd_fuse_volume && \
    # mkdir -p /volumeG/rar2fs_fuse_volume &&\
    # mkdir -p /volumeG/bindfs_fuse_volume

# KODI SOFT AND REPOS
RUN cd /mounts/kodi/software && wget https://kodi.jellyfin.org/repository.jellyfin.kodi.zip 
RUN cd /mounts/kodi/software && wget https://github.com/fandangos/JRE-Kodi-Android/releases/download/1.2-aarch64/script.service.jre-aarch64-v1.2.zip 
RUN cd /mounts/kodi/software && wget https://jurialmunkey.github.io/repository.jurialmunkey/repository.jurialmunkey-3.4.zip
RUN cd /mounts/kodi/software && wget https://a4k-openproject.github.io/a4kSubtitles/packages/a4kSubtitles-repository.zip
RUN cd /mounts/kodi/software && wget https://abratchik.github.io/kodi.repository/leia/script.unlock.advancedsettings/script.unlock.advancedsettings-1.0.3.zip

# copy conf and s6 scripts from repo
# COPY rclone.conf /root/.config/rclone/
COPY root/requirements.txt /requirements.txt

# fix of https://github.com/philamp/jellygrail/issues/2 (+l49)
RUN python3 -m venv /opt/venv
RUN /opt/venv/bin/pip install --upgrade pip
RUN /opt/venv/bin/pip install -r /requirements.txt

# Définir le chemin de l'environnement virtuel
ENV PATH="/opt/venv/bin:$PATH"

# nginx
RUN apt-get -y install nginx nginx-extras unzip
    
# COPY webdav.conf /etc/nginx/conf.d/default.conf -- now done in init
RUN rm /etc/nginx/sites-enabled/*

# ADB
RUN wget https://dl.google.com/android/repository/platform-tools-latest-linux.zip && \
    unzip platform-tools-latest-linux.zip && \
    rm platform-tools-latest-linux.zip
    # cd platform-tools/

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
    git clone https://github.com/philamp/bindfs_jelly.git . && \
    mkdir build && \
    cd build && \
    cmake .. && \
    make clean all install && \
    rm -rf $WORKDIR

# create a ffprobe symlink
RUN cd /usr/local/bin && \
    ln -s /usr/lib/jellyfin-ffmpeg/ffprobe ffprobe
    
# copy the rest
COPY root/ /
RUN chmod u+x /init

# expose nginx
EXPOSE 8085

# expose adb if needed
# EXPOSE 5037

# expose 6502 jelly_update script
EXPOSE 6502

# overwrite run jellyfin main original process as CMD instead of entrypoint
ENTRYPOINT ["/init"]
# CMD ["/bin/bash"]
CMD ["python3", "/usr/local/bin/grail_jelly/main.py"]
