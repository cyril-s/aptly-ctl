FROM debian:stretch
ENV GPG_KEY=DC3CFE1DD8562BB86BF3845A4E15F887476CCCE0
ENV GPG_PASS=aptlyctltest
RUN apt-get update && apt-get -y install aptly bzip2 gnupg gpgv sudo
RUN adduser --gecos "" --disabled-password aptly
WORKDIR /home/aptly
ADD --chown=aptly:aptly aptly-ctl-test.asc ./
USER aptly
RUN echo "$GPG_PASS" | tee /home/aptly/gpg_pass
RUN mkdir /home/aptly/.gnupg && chmod 0700 /home/aptly/.gnupg
RUN echo "pinentry-mode loopback" | tee -a /home/aptly/.gnupg/gpg.conf
RUN gpg --batch --passphrase "$GPG_PASS" --import aptly-ctl-test.asc
RUN echo "$GPG_KEY:6:" | gpg --batch --import-ownertrust
RUN aptly repo create -component=main -distribution=stretch stretch_main
RUN aptly repo create -component=extra -distribution=stretch stretch_extra
RUN aptly publish repo -batch -gpg-key=$GPG_KEY -passphrase "$GPG_PASS" -architectures=amd64 stretch_main
EXPOSE 8090
ENTRYPOINT ["/usr/bin/aptly", "api", "serve"]
CMD ["-listen=:8090"]
