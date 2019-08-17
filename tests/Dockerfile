FROM debian:buster

ENV GPG_KEY=DC3CFE1DD8562BB86BF3845A4E15F887476CCCE0 \
    GPG_PASS=aptlyctltest \
    DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8

RUN apt-get update && apt-get -y install \
	bzip2 \
	gnupg1 \
	gpgv1 \
	sudo

RUN echo "deb http://repo.aptly.info/ squeeze main" >> /etc/apt/sources.list && \
    apt-key adv --keyserver pool.sks-keyservers.net --recv-keys ED75B5A4483DA07C

RUN apt-get update && apt-get -y install aptly && \
    adduser --gecos "" --disabled-password aptly && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /home/aptly
ADD --chown=aptly:aptly tests/aptly-ctl-test.asc ./
USER aptly

#echo "pinentry-mode loopback" | tee -a /home/aptly/.gnupg/gpg.conf && \
RUN echo "$GPG_PASS" | tee /home/aptly/gpg_pass && \
    mkdir /home/aptly/.gnupg && chmod 0700 /home/aptly/.gnupg && \
    gpg1 --batch --passphrase "$GPG_PASS" --import aptly-ctl-test.asc && \
    echo "$GPG_KEY:6:" | gpg1 --batch --import-ownertrust && \
    gpg1 -k

#RUN aptly repo create -component=main -distribution=stretch stretch_main && \
#    aptly repo create -component=extra -distribution=stretch stretch_extra && \
#    aptly publish repo -batch -gpg-key=$GPG_KEY -passphrase "$GPG_PASS" -architectures=amd64 stretch_main

EXPOSE 8090
ENTRYPOINT ["/usr/bin/aptly", "api", "serve"]
CMD ["-listen=:8090"]
