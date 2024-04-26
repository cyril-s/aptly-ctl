FROM debian:bookworm

ARG APTLY_VERSION=1.4.0

ENV GPG_KEY=DC3CFE1DD8562BB86BF3845A4E15F887476CCCE0 \
    GPG_PASS=aptlyctltest \
    DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8

ADD https://www.aptly.info/pubkey.txt /etc/apt/trusted.gpg.d/aptly.asc

RUN echo "deb http://repo.aptly.info/ squeeze main" >> /etc/apt/sources.list && \
    chmod a+r /etc/apt/trusted.gpg.d/aptly.asc && \
    echo "Package: aptly\nPin: origin repo.aptly.info\nPin-Priority: 990" > /etc/apt/preferences.d/01aptly && \
    cat /etc/apt/preferences.d/01aptly && \
    apt update && \
    apt -y install aptly="$APTLY_VERSION" gnupg gpg bzip2 xz-utils && \
    adduser --gecos "" --disabled-password aptly && \
    apt-get clean && rm -rf /var/lib/apt/lists/*


WORKDIR /home/aptly
COPY --chown=aptly:aptly tests/aptly-ctl-test.asc ./
USER aptly

#echo "pinentry-mode loopback" | tee -a /home/aptly/.gnupg/gpg.conf && \
RUN echo "$GPG_PASS" | tee gpg_pass && \
    mkdir .gnupg && chmod 0700 .gnupg && \
    gpg --batch --passphrase "$GPG_PASS" --import aptly-ctl-test.asc && \
    echo "$GPG_KEY:6:" | gpg --batch --import-ownertrust && \
    gpg -k

#RUN aptly repo create -component=main -distribution=stretch stretch_main && \
#    aptly repo create -component=extra -distribution=stretch stretch_extra && \
#    aptly publish repo -batch -gpg-key=$GPG_KEY -passphrase "$GPG_PASS" -architectures=amd64 stretch_main

EXPOSE 8090
ENTRYPOINT ["/usr/bin/aptly", "api", "serve"]
CMD ["-listen=:8090"]
