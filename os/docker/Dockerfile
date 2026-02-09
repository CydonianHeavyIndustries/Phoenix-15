FROM debian:bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    live-build \
    debootstrap \
    xorriso \
    syslinux \
    grub-pc-bin \
    grub-efi-amd64-bin \
    mtools \
    dosfstools \
    squashfs-tools \
    rsync \
    curl \
    ca-certificates \
    bash \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /work
