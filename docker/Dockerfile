FROM jellyfin/jellyfin:10.10.7 AS imgproxbuilder

# CONSTANTS
ENV GO_VERSION=1.25.0
ENV DEBIAN_FRONTEND=noninteractive
ENV VIPS_VERSION=8.17.1
ENV IMGPROXY_VERSION=3.29.1

# update + CA certs
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates

# Build tools
RUN apt-get install -y --no-install-recommends \
    build-essential pkg-config ninja-build python3 meson \
    bc wget curl git

# LIBVIPS Deps
RUN apt-get install -y --no-install-recommends \
    build-essential pkg-config meson ninja-build libcgif-dev\
    libglib2.0-dev libexpat1-dev libexif-dev libpng-dev libjpeg62-turbo-dev \
    libtiff-dev libwebp-dev libgif-dev libopenjp2-7-dev libheif-dev \
    liborc-0.4-dev libpango1.0-dev librsvg2-dev \
    libopenexr-dev libmatio-dev libgsf-1-dev libraw-dev libcfitsio-dev \
    liblcms2-dev libimagequant-dev libfftw3-dev

# LIBVIPS build (with meson)
RUN set -eux; \
    workdir="$(mktemp -d)" && cd "$workdir" && \
    wget -q "https://github.com/libvips/libvips/releases/download/v${VIPS_VERSION}/vips-${VIPS_VERSION}.tar.xz" && \
    tar xf "vips-${VIPS_VERSION}.tar.xz" && \
    cd "vips-${VIPS_VERSION}" && \
    meson setup build \
      --prefix=/usr/local \
      --libdir=lib \
      --buildtype=release \
      -Dintrospection=disabled && \
    meson compile -C build && \
    meson test -C build && \
    meson install -C build && \
    ldconfig && \
    rm -rf "$workdir"

# GO install
RUN set -eux; \
    workdir="$(mktemp -d)" && cd "$workdir" && \
    wget -q "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" && \
    tar -C /usr/local -xzf "go${GO_VERSION}.linux-amd64.tar.gz" && \
    rm -rf "$workdir"
ENV PATH="/usr/local/go/bin:${PATH}"

# Ensure LIBVIPS is found later by imgproxy through pkgconfig
ENV PKG_CONFIG_PATH="/usr/local/lib/pkgconfig:/usr/lib/pkgconfig"
ENV LD_LIBRARY_PATH="/usr/local/lib:${LD_LIBRARY_PATH}"

# IMGPROXY build
RUN set -eux; \
    WORKDIR=`mktemp -d` && \
    cd $WORKDIR && \
    curl -Ls https://github.com/imgproxy/imgproxy/archive/v${IMGPROXY_VERSION}.tar.gz \
    | tar -xz --strip-components 1 -C . && \
    CGO_LDFLAGS_ALLOW="-s|-w" \
    go build -o /usr/local/bin/imgproxy && \
    ldconfig && \
    rm -rf $WORKDIR

# .so libs collecting to copy later in runtime image (imgproxy + libvips)
RUN set -eux; \
    mkdir -p /opt/ldd-libs && \
    ldd /usr/local/bin/imgproxy \
    | awk '/=> \// {print $3} /ld-linux/ {print $1}' \
#    | grep -vE '(^|/)ld-linux.*|(^|/)libc\.so|(^|/)libstdc\+\+\.so' \
    | sort -u \
    | xargs -I{} cp -v --parents {} /opt/ldd-libs/

FROM ubuntu AS builder

# RUN apt update && apt install golang libfuse
ENV DEBIAN_FRONTEND=noninteractive
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
ENV DEBIAN_FRONTEND=noninteractive
ENV v_rar2fs=${RAR2FS_VERSION:-1.29.6}
ENV v_unrar=${UNRAR_VERSION:-6.1.3}
ENV S6_OVERLAY_VERSION="3.1.5.0"
ENV S6_OVERLAY_ARCH="x86_64"

# apt get stuff (add jmalloc to improve Jellyfin memory usage)
RUN apt-get update && \
    apt-get -y install xz-utils libjemalloc2 

# ---RCLONE IMPORT----
COPY --from=builder /go/src/github.com/rclone/rclone/rclone /usr/bin/rclone-linux

# -- IMGPROXY + LIBVIPS IMPORT ---
COPY --from=imgproxbuilder /usr/local/bin/imgproxy /usr/local/bin/imgproxy
COPY --from=imgproxbuilder /usr/local/lib /usr/local/lib
# imgprox deps copy
COPY --from=imgproxbuilder /opt/ldd-libs /opt/ldd-libs
RUN set -eux; \
    mkdir -p /usr/lib /usr/lib64 || true; \ 
    if [ -d /opt/ldd-libs/usr ]; then cp -a /opt/ldd-libs/usr/* /usr/; fi; \
    if [ -d /opt/ldd-libs/lib ]; then cp -a /opt/ldd-libs/lib/* /usr/lib/; fi; \
    if [ -d /opt/ldd-libs/lib64 ]; then cp -a /opt/ldd-libs/lib64/* /usr/lib64/; fi; \
    rm -rf /opt/ldd-libs

ENV LD_LIBRARY_PATH="/usr/local/lib:${LD_LIBRARY_PATH}"
RUN ldconfig

# verif its allright
RUN ldd /usr/local/bin/imgproxy | awk '/not found/ {nf=1} END {exit nf}'


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
RUN chmod ugo+rx /usr/bin/rclone-linux

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
    
# copy the rest and set executable to scripts
COPY root/ /
RUN chmod u+x /init
RUN chmod +x /etc/cont-init.d/*
RUN chmod -R +x /etc/s6-overlay/s6-rc.d
RUN chmod +x /kodi_addons.sh
RUN chmod +x /usr/local/bin/early_init.sh
RUN chmod +x /usr/local/bin/grail_jelly/main.py

# insert source to earl_init.sh in s6-overlay /init
RUN sed -i '1a\
. /usr/local/bin/early_init.sh' /init

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

# Expose service ports (nginx, ssh, mariadb, grail_jelly)
EXPOSE 8085
#EXPOSE 23
EXPOSE 6502
EXPOSE 6503

# overwrite run jellyfin main original process as CMD instead of entrypoint
ENTRYPOINT ["/init"]
CMD ["python3", "/usr/local/bin/grail_jelly/main.py"]

# CMD ["/bin/bash"]
