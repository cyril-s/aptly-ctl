# __aptly-ctl__ -- Convenient aptly API client

__aptly-ctl__ is a command line tool for managing [aplty](https://www.aptly.info/) repositories remotely via [API](https://www.aptly.info/doc/api/). This tool tries to group most common repository operations into composite ones, more convenient for humans, and maintain ability to perform any atomic API request at the same time. __aptly-ctl__ is built upon [aptly-api-client](https://github.com/gopythongo/aptly-api-client) library and MIT licensed.

***

## Features
* `put` subcommand uploads deb package to aptly instance, adds it to specified local repo and updates all publishes that depend on that local repo;
* `remove` subcommand removes deb packages from local repos and updates publishes that depend on those repos;
* `search` subcommand is self-explanatory. Is searches using [aptly package query format](https://www.aptly.info/doc/feature/query/);
* `copy` subcommand copies packages between local repos and updates dependent publishes;
* `repo` and `publish` subcommand are intended to perform atomic API operations like creation, deletion etc.

## Installation
```bash
$ pip3 install aptly-ctl
```
or from source code directory
```bash
$ python3 setup.py install
```

## Usage
__aptly-ctl__ has the following config format:
```yaml
profiles:
  - name: local
    url: http://localhost:8090/api
    signing:
      gpgkey: "DC3CFE1DD8562BB86BF3845A4E15F887476CCCE0"
      passphrase: "secret"
  - name: remote
    url: http://user:password@remote:8090/api
    signing:
      gpgkey: "maintainer@somerepo.org"
      passphrase_file: "/etc/aptly/gpg_pass"
    signing_overrides:
      "./stretch":
        skip: true
```
Each `profile` element describes configuration for one aptly instance. By default, __aptly-ctl__ uses the first one listed. To select profile, use `-p` or `--profile` argument to select by position (e.g. `-p 0`, `--profile 1`), by name (e.g. `--profile local`) or by partial name match (`-p l` or `-p r` would suffice for this case). `url` is an aplty API endpoint to connect to. `signing` is a default signing config. It may contain
* `skip` -- skip signing at all. Default: `true`;
* `batch` -- enable batch mode used when passing passphraze. Generally you want it always `true`. Default: `true`;
* `gpgkey` -- gpg key name (key fingerprint or email). No default;
* `keyring` -- gpg keyring file name local to server. Default: gpg defaults;
* `secret_keyring` -- gpg secret keyring file name local to server. Default: gpg defaults;
* `passphrase` -- gpg key passphrase. No default;
* `passphrase_file` -- gpg passphrase file local to server. No default.

`signing_overrides` dictionary is optional and used to override default signing config for some publishes. Specify publish in form `[<storage>:]<prefix>/<distribution>`. Root prefix is `.`. Configuration is the same as for `signing`.

To specify config location use `-c` argument, or save it in one of the following locations (using the first found, searching from the first to the last):
1. $HOME/aptly-ctl.yml;
2. $HOME/aptly-ctl.yaml;
3. $HOME/aptly-ctl.conf;
4. $HOME/.aptly-ctl.yml;
5. $HOME/.aptly-ctl.yaml;
6. $HOME/.aptly-ctl.conf;
7. $HOME/.config/aptly-ctl.yml;
8. $HOME/.config/aptly-ctl.yaml;
9. $HOME/.config/aptly-ctl.conf;
10. /etc/aptly-ctl.yml;
11. /etc/aptly-ctl.yaml;
12. /etc/aptly-ctl.conf.

If __aptly-ctl__ cannot find config in listed locations, you can specify configuration keys on command line and still have a valid config which allows to run __aptly-ctl__ without config at all. Specify them usging `-C <key>=<value>` argument, where `<key>` components are separated by a dot e.g.
```bash
$ aptly-ctl -C "url=http://localhost:8090/api" -C "signing.skip=true" repo list
```

Some __aptly-ctl__ subcommands print to STDOUT output parsable by other subcommands. Check out subcommand's `--help` to get some hints on how to use it in conjunction with other ones.

### Examples
Search for a package containing 'nginx':
```bash
$ aptly-ctl search 'Name (~ nginx)'
"jessie_main_stable/Pamd64 nginx-full-dbg 1.9.9-2~didww+8.2 c89ebe5a0ac7e146"
"jessie_main_stable/Pamd64 nginx-full-dbg 1.10.0-0~didww+8.4 25d7ab9574e3de74"
"jessie_main_stable/Pamd64 nginx-full-dbg 1.10.1-0~didww+8.4 1cc12f74c9a28368"
"jessie_main_stable/Pamd64 nginx-light 1.9.9-2~didww+8.2 d34ac5a2789f3126"
"jessie_main_stable/Pamd64 nginx-light 1.10.0-0~didww+8.4 c154f10a23232451"
"jessie_main_stable/Pamd64 nginx-light 1.10.1-0~didww+8.4 3f9d1d3d63a569e6"
"jessie_main_stable/Pamd64 nginx-light-dbg 1.9.9-2~didww+8.2 ba326e19379f7be"
"jessie_main_stable/Pamd64 nginx-light-dbg 1.10.0-0~didww+8.4 a5069fb4d70aab16"
"jessie_main_stable/Pamd64 nginx-light-dbg 1.10.1-0~didww+8.4 b57b8645f8d17e26"
"jessie_main_stable/Pamd64 nginx-naxsi 1.9.9-2~didww+8.2 868e43c45e4f8493"
"jessie_main_stable/Pamd64 nginx-naxsi 1.10.0-0~didww+8.4 7a51d45d80536ce5"
"jessie_main_stable/Pamd64 nginx-naxsi 1.10.1-0~didww+8.4 907034c9442a2ca9"
"jessie_main_stable/Pamd64 nginx-naxsi-dbg 1.9.9-2~didww+8.2 3b51a3c9d9031da5"
"jessie_main_stable/Pamd64 nginx-naxsi-dbg 1.10.0-0~didww+8.4 9cb058b4ce84d690"
"jessie_main_stable/Pamd64 nginx-naxsi-dbg 1.10.1-0~didww+8.4 ccc5f79434c67dec"
"stretch_main_stable/Pamd64 libnginx-mod-http-auth-pam 1.12.0 78c35d6a10bead1"
"stretch_main_stable/Pamd64 libnginx-mod-http-auth-pam-dbgsym 1.12.0 3aca8eef59f9216"
"stretch_main_stable/Pamd64 libnginx-mod-http-cache-purge 1.12.0 ffe2d6f3c00a1dbe"
"stretch_main_stable/Pamd64 libnginx-mod-http-cache-purge-dbgsym 1.12.0 658e2d13463bf4ac"
```
or
```bash
$ aptly-ctl search --name nginx
```
Remove particular packages:
```bash
$ aptly-ctl remove \
"stretch_main_stable/Pamd64 libnginx-mod-http-cache-purge-dbgsym 1.12.0 658e2d13463bf4ac" \
"jessie_main_stable/Pamd64 nginx-light-dbg 1.9.9-2~didww+8.2 ba326e19379f7be"
```
Verbosely upload packages from local file system to aptly, add them to specified repo and update it's publish:
```bash
$ aptly-ctl -v put stretch_main packages/*
INFO put(6860) Loadded config from "/etc/aptly-ctl.yml"
INFO put(6860) Running put subcommand.
INFO put(6860) Uploading the packages to directory "stretch_main_1537258123"
INFO put(6860) Deleting directory 'stretch_main_1537258123'.
"stretch_main/Pamd64 libnginx-mod-http-auth-pam 1.12.0 78c35d6a10bead1"
"stretch_main/Pamd64 libnginx-mod-http-cache-purge 1.12.0 ffe2d6f3c00a1dbe"
"stretch_main/Pamd64 libnginx-mod-http-dav-ext 1.12.0 1d4bed1e2358a7ad"
INFO put(6860) Updating publish with prefix ".", dist "stretch"
INFO put(6860) Updated publish with prefix ".", dist "stretch".
```
Upload packages without config file (e.g. from CI server):
```bash
$ aptly-ctl \
-C "url=http://user:pass@repo.example.org:8090/api" \
-C "signing.gpgkey=me@example.org" \
-C "signing.passphrase_file=/etc/gpg_pass" \
put my_repo *.deb
```
Leave only 2 most recent versions of a package `nginx-full` in repo `stretch_main` and do it verbosely:
```bash
$ aptly-ctl -v search -r stretch_main --rotate 2 nginx-full | aptly-ctl -v remove
INFO remove(6946) Loadded config from "/etc/aptly-ctl.yml"
INFO remove(6946) Running remove subcommand.
INFO search(6945) Loadded config from "/etc/aptly-ctl.yml"
INFO search(6945) Running search subcommand.
INFO search(6945) Searching in repos stretch_main
INFO search(6945) Query: nginx-full
INFO remove(6946) Removed "Pamd64 nginx-full 1.13.4-1 6173d29295cbacab" from stretch_main
INFO remove(6946) Removed "Pamd64 nginx-full 1.13.5-1 3b1dc91fbe2a9254" from stretch_main
INFO remove(6946) Removed "Pi386 nginx-full 1.13.4-1 39fbaa9e4fcd58e3" from stretch_main
INFO remove(6946) Removed "Pi386 nginx-full 1.13.5-1 2b3998898bb9e56d" from stretch_main
INFO remove(6946) Updating publish with prefix ".", dist "stretch"
INFO remove(6946) Updated publish with prefix ".", dist "stretch".
```
Publish local repo `stretch_extra`:
```bash
$ aptly-ctl publish create -s local --architectures amd64 extra/stretch stretch_extra=extra
extra/stretch
    Source kind: local
    Prefix: extra
    Distribution: stretch
    Storage:
    Label:
    Origin:
    Architectures: amd64
    Sources:
        stretch_extra (extra)
```
