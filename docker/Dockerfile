# syntax=docker/dockerfile:1.7

ARG JELLYFIN_VERSION=10.10.7
ARG UBUNTU_VERSION=24.04

ARG GO_VERSION=1.25.0
ARG RCLONE_GO_VERSION=1.22.12
ARG VIPS_VERSION=8.17.1
ARG IMGPROXY_VERSION=3.29.1
ARG RAR2FS_VERSION=1.29.6
ARG UNRAR_VERSION=6.1.3
ARG S6_OVERLAY_VERSION=3.2.1.0

############################
# GO TOOLCHAIN
############################
FROM --platform=$BUILDPLATFORM golang:${GO_VERSION}-bookworm AS go-toolchain

############################
# IMGPROXY + LIBVIPS BUILDER
############################
FROM --platform=$TARGETPLATFORM jellyfin/jellyfin:${JELLYFIN_VERSION} AS imgproxy-builder

ARG DEBIAN_FRONTEND=noninteractive
ARG VIPS_VERSION
ARG IMGPROXY_VERSION
ARG TARGETOS
ARG TARGETARCH

ENV PKG_CONFIG_PATH=/usr/local/lib/pkgconfig:/usr/lib/pkgconfig
ENV LD_LIBRARY_PATH=/usr/local/lib
ENV PATH=/usr/local/go/bin:$PATH
ENV CGO_ENABLED=1

COPY --from=go-toolchain /usr/local/go /usr/local/go

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        build-essential \
        pkg-config \
        ninja-build \
        python3 \
        meson \
        bc \
        wget \
        curl \
        git \
        libcgif-dev \
        libglib2.0-dev \
        libexpat1-dev \
        libexif-dev \
        libpng-dev \
        libjpeg62-turbo-dev \
        libtiff-dev \
        libwebp-dev \
        libgif-dev \
        libopenjp2-7-dev \
        libheif-dev \
        liborc-0.4-dev \
        libpango1.0-dev \
        librsvg2-dev \
        libopenexr-dev \
        libmatio-dev \
        libgsf-1-dev \
        libraw-dev \
        libcfitsio-dev \
        liblcms2-dev \
        libimagequant-dev \
        libfftw3-dev; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /src

RUN set -eux; \
    workdir="$(mktemp -d)"; \
    cd "$workdir"; \
    wget -q "https://github.com/libvips/libvips/releases/download/v${VIPS_VERSION}/vips-${VIPS_VERSION}.tar.xz"; \
    tar xf "vips-${VIPS_VERSION}.tar.xz"; \
    cd "vips-${VIPS_VERSION}"; \
    meson setup build \
      --prefix=/usr/local \
      --libdir=lib \
      --buildtype=release \
      -Dintrospection=disabled; \
    meson compile -C build; \
    #meson test -C build; \
    meson install -C build; \
    ldconfig; \
    rm -rf "$workdir"

RUN set -eux; \
    go version; \
    pkg-config --cflags glib-2.0; \
    pkg-config --cflags vips; \
    pkg-config --modversion glib-2.0; \
    pkg-config --modversion vips

RUN --mount=type=cache,target=/go/pkg/mod,sharing=locked \
    --mount=type=cache,target=/root/.cache/go-build,sharing=locked \
    set -eux; \
    rm -rf /src/*; \
    git clone --branch "v${IMGPROXY_VERSION}" --depth 1 https://github.com/imgproxy/imgproxy.git .; \
    GOOS=${TARGETOS:-linux} GOARCH=${TARGETARCH} \
    go build -trimpath -ldflags="-s -w" -o /out/imgproxy .

ENV LD_LIBRARY_PATH=/usr/local/lib

RUN set -eux; \
    ldconfig; \
    mkdir -p /opt/ldd-libs; \
    { \
      ldd /out/imgproxy; \
      ldd /usr/local/lib/libvips.so; \
      ldd /usr/local/lib/libvips.so.42; \
      ldd /usr/local/lib/libvips.so.42.19.1; \
    } \
      | awk '/=> \// {print $3} /ld-linux/ {print $1}' \
      | sort -u \
      | xargs -r -I{} cp -v --parents "{}" /opt/ldd-libs/

############################
# IMGPROXY PACKAGER
############################
FROM --platform=$TARGETPLATFORM jellyfin/jellyfin:${JELLYFIN_VERSION} AS imgproxy-packager

COPY --from=imgproxy-builder /usr/local /usr/local
COPY --from=imgproxy-builder /out/imgproxy /usr/local/bin/imgproxy
COPY --from=imgproxy-builder /opt/ldd-libs /opt/ldd-libs


############################
# RCLONE BUILDER
############################
FROM --platform=$BUILDPLATFORM golang:${RCLONE_GO_VERSION}-bookworm AS rclone-builder

ARG TARGETOS
ARG TARGETARCH

WORKDIR /src

RUN --mount=type=cache,target=/go/pkg/mod,sharing=locked \
    --mount=type=cache,target=/root/.cache/go-build,sharing=locked \
    git clone --branch master --depth 1 https://github.com/philamp/rclone_jelly.git .

RUN --mount=type=cache,target=/go/pkg/mod,sharing=locked \
    --mount=type=cache,target=/root/.cache/go-build,sharing=locked \
    set -eux; \
    CGO_ENABLED=0 GOOS=${TARGETOS:-linux} GOARCH=${TARGETARCH} make; \
    ./rclone version; \
    install -Dm755 ./rclone /out/rclone-linux

############################
# RAR2FS / UNRAR BUILDER
############################
FROM --platform=$TARGETPLATFORM jellyfin/jellyfin:${JELLYFIN_VERSION} AS rar2fs-builder

ARG DEBIAN_FRONTEND=noninteractive
ARG RAR2FS_VERSION
ARG UNRAR_VERSION

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        wget \
        make \
        g++ \
        fuse \
        libfuse-dev; \
    rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    workdir="$(mktemp -d)"; \
    cd "$workdir"; \
    wget "https://www.rarlab.com/rar/unrarsrc-${UNRAR_VERSION}.tar.gz"; \
    tar zxf "unrarsrc-${UNRAR_VERSION}.tar.gz"; \
    cd unrar; \
    make -j"$(nproc)"; \
    make install; \
    make lib; \
    make install-lib; \
    cd "$workdir"; \
    wget "https://github.com/hasse69/rar2fs/releases/download/v${RAR2FS_VERSION}/rar2fs-${RAR2FS_VERSION}.tar.gz" -O rar2fs.tar.gz; \
    tar zxf rar2fs.tar.gz; \
    cd "rar2fs-${RAR2FS_VERSION}"; \
    ./configure --with-unrar=../unrar --with-unrar-lib=/usr/lib/; \
    make -j"$(nproc)"; \
    make install; \
    mkdir -p /out/bin /out/lib; \
    cp -av /usr/local/bin/rar2fs /out/bin/; \
    cp -av /usr/bin/unrar /out/bin/ || cp -av /usr/local/bin/unrar /out/bin/; \
    ldd /usr/local/bin/rar2fs | awk '/=> \// {print $3}' | sort -u | xargs -r -I{} cp -v --parents "{}" /out/lib/; \
    rm -rf "$workdir"

############################
# BINDFS BUILDER
############################
FROM jellyfin/jellyfin:${JELLYFIN_VERSION} AS bindfs-builder

ARG DEBIAN_FRONTEND=noninteractive

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        build-essential \
        pkg-config \
        git \
        autoconf \
        libtool \
        libfuse3-dev \
        libsqlite3-dev \
        cmake; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN git clone --branch master --depth 1 https://github.com/philamp/bindfs_jelly.git .

RUN set -eux; \
    cmake -S . -B build \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_C_FLAGS="-D_FILE_OFFSET_BITS=64" \
      -DCMAKE_CXX_FLAGS="-D_FILE_OFFSET_BITS=64"; \
    cmake --build build -j"$(nproc)"; \
    DESTDIR=/out cmake --install build

############################
# FFPROBE WRAPPER BUILDER
############################
FROM --platform=$TARGETPLATFORM ubuntu:${UBUNTU_VERSION} AS ffprobe-wrapper-builder

ARG DEBIAN_FRONTEND=noninteractive

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends gcc libc6-dev; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY root/usr/local/bin/ffprobe_wrapper/ffprobew.c /src/ffprobew.c

RUN set -eux; \
    mkdir -p /out; \
    gcc -O2 -o /out/ffprobew ffprobew.c

############################
# PYTHON VENV BUILDER
############################
FROM --platform=$TARGETPLATFORM jellyfin/jellyfin:${JELLYFIN_VERSION} AS python-builder

ARG DEBIAN_FRONTEND=noninteractive

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        build-essential \
        pkg-config \
        libffi-dev \
        libssl-dev; \
    rm -rf /var/lib/apt/lists/*

COPY root/requirements.txt /requirements.txt

RUN set -eux; \
    python3 -m venv /opt/venv; \
    /opt/venv/bin/pip install --upgrade pip setuptools wheel; \
    /opt/venv/bin/pip install --no-cache-dir -r /requirements.txt

############################
# FINAL RUNTIME
############################
FROM --platform=$TARGETPLATFORM jellyfin/jellyfin:${JELLYFIN_VERSION}

ARG DEBIAN_FRONTEND=noninteractive
ARG S6_OVERLAY_VERSION
ARG TARGETARCH

ENV MYSQL_DIR=/jellygrail/data/mariadb
ENV DATADIR=/jellygrail/data/mariadb/databases
ENV PATH=/opt/venv/bin:$PATH
ENV LD_LIBRARY_PATH=/usr/local/lib
ENV S6_OVERLAY_VERSION=${S6_OVERLAY_VERSION}

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        xz-utils \
        libjemalloc2 \
        python3 \
        python3-venv \
        fuse \
        libfuse-dev \
        libfuse3-dev \
        nginx \
        nginx-extras \
        unzip \
        mariadb-server \
        netcat-openbsd \
        wget \
        ca-certificates; \
    rm -rf /var/lib/apt/lists/*

# rclone
COPY --from=rclone-builder /out/rclone-linux /usr/bin/rclone-linux

# imgproxy + libvips
COPY --from=imgproxy-packager /usr/local /usr/local
COPY --from=imgproxy-packager /opt/ldd-libs /opt/ldd-libs

RUN set -eux; \
    mkdir -p /usr/lib /usr/lib64 /lib /lib64; \
    if [ -d /opt/ldd-libs/usr ]; then cp -a /opt/ldd-libs/usr/* /usr/; fi; \
    if [ -d /opt/ldd-libs/lib ]; then cp -a /opt/ldd-libs/lib/* /lib/; fi; \
    if [ -d /opt/ldd-libs/lib64 ]; then cp -a /opt/ldd-libs/lib64/* /lib64/; fi; \
    ldconfig; \
    rm -rf /opt/ldd-libs

# python venv
COPY --from=python-builder /opt/venv /opt/venv

# rar2fs
COPY --from=rar2fs-builder /out/bin/rar2fs /usr/local/bin/rar2fs
COPY --from=rar2fs-builder /out/bin/unrar /usr/local/bin/unrar
COPY --from=rar2fs-builder /out/lib /tmp/rar2fs-lib

RUN set -eux; \
    if [ -d /tmp/rar2fs-lib/lib ]; then cp -a /tmp/rar2fs-lib/lib/* /lib/; fi; \
    if [ -d /tmp/rar2fs-lib/usr ]; then cp -a /tmp/rar2fs-lib/usr/* /usr/; fi; \
    if [ -d /tmp/rar2fs-lib/lib64 ]; then cp -a /tmp/rar2fs-lib/lib64/* /lib64/; fi; \
    rm -rf /tmp/rar2fs-lib; \
    ldconfig

# bindfs
COPY --from=bindfs-builder /out/ /

# ffprobe wrapper
COPY --from=ffprobe-wrapper-builder /out/ffprobew /usr/local/bin/ffprobew

# s6 overlay multi-arch
RUN set -eux; \
    case "${TARGETARCH}" in \
      amd64) s6_arch="x86_64" ;; \
      arm64) s6_arch="aarch64" ;; \
      arm/v7|arm) s6_arch="arm" ;; \
      *) echo "Unsupported TARGETARCH=${TARGETARCH}"; exit 1 ;; \
    esac; \
    cd /tmp; \
    wget -q "https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz"; \
    tar -C / -Jxpf s6-overlay-noarch.tar.xz; \
    wget -q "https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${s6_arch}.tar.xz"; \
    tar -C / -Jxpf "s6-overlay-${s6_arch}.tar.xz"; \
    rm -f /tmp/s6-overlay-*.tar.xz

COPY root/ /

RUN set -eux; \
    chmod ugo+rx /usr/bin/rclone-linux; \
    chmod +x /init /kodi_addons.sh /early_init.sh /mountspecific.sh /unmountspecific.sh; \
    chmod -R +x /etc/s6-overlay/s6-rc.d; \
    chmod +x /usr/local/bin/grail_jelly/newmain.py; \
    sed -i '1a\
. /early_init.sh' /init; \
    mv /usr/lib/jellyfin-ffmpeg/ffprobe /usr/lib/jellyfin-ffmpeg/ffprober; \
    cp /usr/local/bin/ffprobew /usr/lib/jellyfin-ffmpeg/ffprobe; \
    ln -sf /usr/lib/jellyfin-ffmpeg/ffprober /usr/local/bin/ffprober; \
    ln -sf /usr/lib/jellyfin-ffmpeg/ffprobe /usr/local/bin/ffprobe; \
    rm -f /etc/nginx/sites-enabled/*; \
    ldconfig

EXPOSE 8085 6502 6503 8089

ENTRYPOINT ["/init"]
CMD ["python3", "/usr/local/bin/grail_jelly/newmain.py"]