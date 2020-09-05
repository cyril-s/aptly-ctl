import logging
import re
import os
import urllib3  # type: ignore
import json
import hashlib
import fnvhash  # type: ignore
from datetime import datetime
import dateutil.parser
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import (
    Any,
    ClassVar,
    Dict,
    Iterable,
    List,
    NamedTuple,
    Optional,
    Sequence,
    Tuple,
    Union,
    cast,
)
from aptly_ctl.exceptions import AptlyApiError
from aptly_ctl.debian import Version, get_control_file_fields
from aptly_ctl.util import urljoin, timedelta_pretty

log = logging.getLogger(__name__)

KEY_REGEXP = re.compile(r"(\w*?)P(\w+) (\S+) (\S+) (\w+)$")
DIR_REF_REGEXP = re.compile(r"(\S+?)_(\S+?)_(\w+)")


class SigningConfig(NamedTuple):
    skip: bool = False
    batch: bool = True
    gpgkey: Optional[str] = None
    keyring: Optional[str] = None
    secret_keyring: Optional[str] = None
    passphrase: Optional[str] = None
    passphrase_file: Optional[str] = None

    @property
    def kwargs(self) -> Dict[str, Union[str, bool]]:
        if self.skip:
            return {"Skip": True}
        kwargs = {"Batch": self.batch}  # type: Dict[str, Union[str, bool]]
        if self.gpgkey:
            kwargs["GpgKey"] = self.gpgkey
        if self.keyring:
            kwargs["Keyring"] = self.keyring
        if self.secret_keyring:
            kwargs["SecretKeyring"] = self.secret_keyring
        if self.passphrase:
            kwargs["Passphrase"] = self.passphrase
        if self.passphrase_file:
            kwargs["PassphraseFile"] = self.passphrase_file
        return kwargs


DefaultSigningConfig = SigningConfig()


class PackageFileInfo(NamedTuple):
    filename: str
    path: str
    origpath: str
    size: int
    md5: str
    sha1: str
    sha256: str


class Package(NamedTuple):
    """Represents package in aptly or in local filesystem"""

    name: str
    version: Version
    arch: str
    prefix: str
    files_hash: str
    fields: Optional[Dict[str, str]] = None
    file: Optional[PackageFileInfo] = None

    @property
    def key(self) -> str:
        """Returns aptly key"""
        return "{o.prefix}P{o.arch} {o.name} {o.version} {o.files_hash}".format(o=self)

    @property
    def dir_ref(self) -> str:
        """Returns aptly dir ref"""
        return "{o.name}_{o.version}_{o.arch}".format(o=self)

    @classmethod
    def from_key(cls, key: str) -> "Package":
        """Create from instance of aptly key"""
        match = KEY_REGEXP.match(key)
        if not match:
            raise ValueError("invalid package key '{}'".format(key))
        prefix, arch, name, version_str, files_hash = match.groups()
        version = Version(version_str)
        return cls(
            name=name, version=version, arch=arch, prefix=prefix, files_hash=files_hash
        )

    @classmethod
    def from_file(cls, filepath: str) -> "Package":
        """
        Build representation of aptly package from package on local filesystem
        """
        hashes = [hashlib.md5(), hashlib.sha1(), hashlib.sha256(), hashlib.sha512()]
        size = 0
        buff_size = 1024 * 1024
        with open(filepath, "rb", buff_size) as file:
            while True:
                chunk = file.read(buff_size)
                if not chunk:
                    break
                size += len(chunk)
                for _hash in hashes:
                    _hash.update(chunk)
        fields = get_control_file_fields(filepath)
        name = fields["Package"]
        version = Version(fields["Version"])
        arch = fields["Architecture"]
        fileinfo = PackageFileInfo(
            md5=hashes[0].hexdigest(),
            sha1=hashes[1].hexdigest(),
            sha256=hashes[2].hexdigest(),
            size=size,
            filename=os.path.basename(os.path.realpath(filepath)),
            path=os.path.realpath(os.path.abspath(filepath)),
            origpath=filepath,
        )
        data = b"".join(
            [
                bytes(fileinfo.filename, "ascii"),
                fileinfo.size.to_bytes(8, "big"),
                bytes(fileinfo.md5, "ascii"),
                bytes(fileinfo.sha1, "ascii"),
                bytes(fileinfo.sha256, "ascii"),
            ]
        )
        files_hash = "{:x}".format(fnvhash.fnv1a_64(data))
        key_fields = ["P" + arch, name, str(version), files_hash]
        fields["Filename"] = fileinfo.filename
        fields["FilesHash"] = files_hash
        fields["Key"] = " ".join(key_fields)
        fields["MD5sum"] = hashes[0].hexdigest()
        fields["SHA1"] = hashes[1].hexdigest()
        fields["SHA256"] = hashes[2].hexdigest()
        fields["SHA512"] = hashes[3].hexdigest()
        fields["ShortKey"] = " ".join(key_fields[:-1])
        fields["Size"] = str(size)
        return cls(
            name=name,
            version=version,
            arch=arch,
            prefix="",
            files_hash=files_hash,
            fields=fields,
            file=fileinfo,
        )

    @classmethod
    def from_api_response(cls, resp: Dict[str, str]) -> "Package":
        pkg = cls.from_key(resp["Key"])
        return pkg._replace(fields=resp)


class Repo(NamedTuple):
    """Represents local repo in aptly"""

    name: str
    comment: str = ""
    default_distribution: str = ""
    default_component: str = ""

    @classmethod
    def from_api_response(cls, resp: Dict[str, str]) -> "Repo":
        """Create repo instance from API json response"""
        kwargs = {}  # type: Dict[str, Any]
        for key, tgt_key in [
            ("Name", "name"),
            ("Comment", "comment"),
            ("DefaultDistribution", "default_distribution"),
            ("DefaultComponent", "default_component"),
        ]:
            if key in resp:
                kwargs[tgt_key] = resp[key]

        return cls(**kwargs)


class Snapshot(NamedTuple):
    """Represents snapshot in aptly"""

    name: str
    description: str = ""
    created_at: Optional[datetime] = None

    @classmethod
    def from_api_response(cls, resp: Dict[str, str]) -> "Snapshot":
        """Create snapshot instance from API json response"""
        created_at = dateutil.parser.isoparse(resp["CreatedAt"])
        return cls(
            name=resp["Name"], description=resp["Description"], created_at=created_at
        )


class Source(NamedTuple):
    """Represents source from which publishes are created"""

    name: str
    component: Optional[str] = None


class Publish(NamedTuple):
    """Represents publish in aptly"""

    source_kind: str
    sources: Iterable[Source]
    storage: str = ""
    prefix: str = ""
    distribution: str = ""
    architectures: Iterable[str] = ()
    label: str = ""
    origin: str = ""
    not_automatic: bool = False
    but_automatic_upgrades: bool = False
    acquire_by_hash: bool = False

    @classmethod
    def from_api_response(cls, resp: Dict[str, Any]) -> "Publish":
        """Create publish instance from API json response"""
        sources = [
            Source(source["Name"], source.get("Component", None))
            for source in resp["Sources"]
        ]
        kwargs = {"sources": sources}  # type: Dict[str, Any]
        for key, tgt_key in [
            ("SourceKind", "source_kind"),
            ("Storage", "storage"),
            ("Prefix", "prefix"),
            ("Distribution", "distribution"),
            ("Architectures", "architectures"),
            ("Label", "label"),
            ("Origin", "origin"),
            ("NotAutomatic", "not_automatic"),
            ("ButAutomaticUpgrades", "but_automatic_upgrades"),
            ("AcquireByHash", "acquire_by_hash"),
        ]:
            if key in resp:
                kwargs[tgt_key] = resp[key]

        return cls(**kwargs)

    @property
    def sources_dict(self) -> List[Dict[str, str]]:
        sources = []
        for source in self.sources:
            s = {"Name": source.name}  # type: Dict[str, str]
            if source.component:
                s["Component"] = source.component
            sources.append(s)
        return sources

    @property
    def api_params(self) -> Dict[str, Any]:
        params = {
            "SourceKind": self.source_kind,
            "Sources": self.sources_dict,
        }  # type: Dict[str, Any]
        if self.distribution:
            params["Distribution"] = self.distribution
        if self.architectures:
            params["Architectures"] = self.architectures
        if self.label:
            params["Label"] = self.label
        if self.origin:
            params["Origin"] = self.origin
        if self.not_automatic is True:
            params["NotAutomatic"] = "yes"
        elif self.not_automatic:
            params["NotAutomatic"] = self.not_automatic
        if self.but_automatic_upgrades is True:
            params["ButAutomaticUpgrades"] = "yes"
        elif self.but_automatic_upgrades:
            params["ButAutomaticUpgrades"] = self.but_automatic_upgrades
        if self.acquire_by_hash:
            params["AcquireByHash"] = self.acquire_by_hash

        return params

    @property
    def full_prefix(self) -> str:
        prefix = self.prefix if self.prefix else "."
        if not self.storage:
            return prefix
        return self.storage + ":" + prefix

    @property
    def full_prefix_escaped(self) -> str:
        prefix = self.full_prefix
        if prefix == ".":
            return ":."
        prefix = prefix.replace("_", "__")
        prefix = prefix.replace("/", "_")
        return prefix


class FilesReport(NamedTuple):
    failed: Sequence[str] = ()
    added: Sequence[str] = ()
    removed: Sequence[str] = ()
    warnings: Sequence[str] = ()


class Client:
    """Aptly API client with more convenient commands"""

    files_url_path: ClassVar[str] = "api/files"
    repos_url_path: ClassVar[str] = "api/repos"
    snapshots_url_path: ClassVar[str] = "api/snapshots"
    publish_url_path: ClassVar[str] = "api/publish"
    packages_url_path: ClassVar[str] = "api/packages"

    def __init__(
        self,
        url: str,
        max_workers: int = 10,
        default_signing_config: SigningConfig = DefaultSigningConfig,
        signing_config_map: Dict[str, SigningConfig] = None,
    ) -> None:
        self.http = urllib3.PoolManager()
        self.url = url
        self.max_workers = max_workers
        self.default_signing_config = default_signing_config
        if signing_config_map:
            self.signing_config_map = signing_config_map
        else:
            self.signing_config_map = {}

    def get_signing_config(
        self, prefix: Optional[str], distribution: Optional[str]
    ) -> SigningConfig:
        if prefix is None:
            prefix = "."
        if distribution is None:
            distribution = ""
        return self.signing_config_map.get(
            prefix + "/" + distribution, self.default_signing_config
        )

    def _request(
        self,
        method: str,
        url: str,
        data: Union[Dict[str, Any], List[Dict[str, Any]]] = None,
        params: Dict[str, str] = None,
        files: Dict[str, Tuple[str, bytes]] = None,
    ) -> Any:
        start = datetime.now()
        if params:
            log.debug("sending %s %s params: %s", method, url, params)
            resp = self.http.request_encode_url(method, url, fields=params)
        elif files:
            filenames = [
                "{} {} bytes".format(file_tuple[0], len(file_tuple[1]))
                for file_tuple in files.values()
            ]
            log.debug("sending %s %s files: %s", method, url, filenames)
            resp = self.http.request_encode_body(method, url, fields=files)
        else:
            encoded_data = (
                json.dumps(data).encode("utf-8") if data is not None else None
            )
            log.debug("sending %s %s data: %s", method, url, encoded_data)
            resp = self.http.request(
                method,
                url,
                body=encoded_data,
                headers={"Content-Type": "application/json"},
            )
        log.debug(
            "response on %s %s took %s returned %s: %s",
            method,
            url,
            timedelta_pretty(datetime.now() - start),
            resp.status,
            resp.data,
        )
        if resp.status < 200 or resp.status >= 300:
            raise AptlyApiError(resp.status, resp.data)
        resp_data = json.loads(resp.data.decode("utf-8"))
        return resp_data

    def files_upload(self, files: Sequence[str], directory: str) -> List[str]:
        url = urljoin(self.url, self.files_url_path, directory)
        fields = {}  # type: Dict[str, Tuple[str, bytes]]
        for fpath in files:
            filename = os.path.basename(fpath)
            with open(fpath, "br") as f:
                fields[filename] = (filename, f.read())
        resp = self._request("POST", url, files=fields)
        return cast(List[str], resp)

    def files_list(self, directory: str) -> List[str]:
        url = urljoin(self.url, self.files_url_path, directory)
        resp = self._request("GET", url)
        return cast(List[str], resp)

    def files_list_dirs(self) -> List[str]:
        resp = self._request("GET", urljoin(self.url, self.files_url_path))
        return cast(List[str], resp)

    def files_delete_dir(self, directory: str) -> None:
        url = urljoin(self.url, self.files_url_path, directory)
        self._request("DELETE", url)

    def files_delete_file(self, directory: str, file: str) -> None:
        url = urljoin(self.url, self.files_url_path, directory, file)
        self._request("DELETE", url)

    def repo_create(
        self,
        name: str,
        comment: str = "",
        default_distribution: str = "",
        default_component: str = "",
    ) -> Repo:
        """
        Creates new local repo

        Arguments:
            name -- local repo name
            comment -- comment for local repo
            default_distribution -- default distribution. When creating publish
                from local repo, this attribute is looked up to determine target
                distribution for publish if it is not supplied explicitly.
            default_component -- default component. When creating publish
                from local repo, this attribute is looked up to determine target
                component for this repo if it is not supplied explicitly.
        """
        body = {"Name": name}
        if comment:
            body["Comment"] = comment
        if default_distribution:
            body["DefaultDistribution"] = default_distribution
        if default_component:
            body["DefaultComponent"] = default_component
        url = urljoin(self.url, self.repos_url_path)
        repo_data = self._request("POST", url, body)
        repo_data = cast(Dict[str, str], repo_data)
        return Repo.from_api_response(repo_data)

    def repo_show(self, name: str) -> Repo:
        """
        Get info about local repo

        Arguments:
            name -- local repo name
        """
        url = urljoin(self.url, self.repos_url_path, name)
        repo_data = self._request("GET", url)
        repo_data = cast(Dict[str, str], repo_data)
        return Repo.from_api_response(repo_data)

    def repo_list(self) -> List[Repo]:
        """Return a list of all the local repos"""
        repo_list = self._request("GET", urljoin(self.url, self.repos_url_path))
        repo_list = cast(List[Dict[str, str]], repo_list)
        return [Repo.from_api_response(repo) for repo in repo_list]

    def repo_edit(
        self,
        name: str,
        comment: str = "",
        default_distribution: str = "",
        default_component: str = "",
    ) -> Repo:
        """
        Edit local repo.

        Arguments:
            name -- local repo name
            comment -- comment for local repo
            default_distribution -- default distribution. When creating publish
                from local repo, this attribute is looked up to determine target
                distribution for publish if it is not supplied explicitly.
            default_component -- default component. When creating publish
                from local repo, this attribute is looked up to determine target
                component for this repo if it is not supplied explicitly.
        """
        body = {}  # type: Dict[str, str]
        if comment:
            body["Comment"] = comment
        if default_distribution:
            body["DefaultDistribution"] = default_distribution
        if default_component:
            body["DefaultComponent"] = default_component
        url = urljoin(self.url, self.repos_url_path, name)
        repo_data = self._request("PUT", url, body)
        repo_data = cast(Dict[str, str], repo_data)
        return Repo.from_api_response(repo_data)

    def repo_delete(self, name: str, force: bool = False) -> None:
        """
        Delete local repo named

        Arguments:
            name -- local repo name
            force -- delete local repo even if it's pointed by a snapshot
        """
        url = urljoin(self.url, self.repos_url_path, name)
        params = {}  # type: Dict[str, str]
        if force:
            params["force"] = "1"
        self._request("DELETE", url, params=params)

    def repo_add_packages(
        self,
        name: str,
        directory: str,
        file: str = "",
        no_remove: bool = False,
        force_replace: bool = False,
    ) -> FilesReport:
        url = urljoin(self.url, self.repos_url_path, name, "file", directory)
        if file:
            url = urljoin(url, file)
        params = {}  # type: Dict[str, str]
        if no_remove:
            params["noRemove"] = "1"
        if force_replace:
            params["forceReplace"] = "1"
        resp = self._request("POST", url, params=params)
        # remove " added" in "Added":["aptly_0.9~dev+217+ge5d646c_i386 added"]
        added = [s.split(" ")[0] for s in resp["Report"]["Added"]]
        return FilesReport(
            failed=resp["FailedFiles"],
            added=added,
            removed=resp["Report"]["Removed"],
            warnings=resp["Report"]["Warnings"],
        )

    def _search(
        self,
        container: str,
        name: str,
        query: str = "",
        with_deps: bool = False,
        details: bool = False,
    ) -> List[Package]:
        if container == "local_repo":
            url = urljoin(self.url, self.repos_url_path, name, "packages")
        elif container == "snapshot":
            url = urljoin(self.url, self.snapshots_url_path, name, "packages")
        else:
            raise ValueError(
                "container argument must be either 'local_repo' or 'snapshot'"
            )
        params = {}
        if query:
            params["q"] = query
        if with_deps:
            params["withDeps"] = "1"
        if details:
            params["format"] = "details"
        resp = self._request("GET", url, params=params)
        if details:
            resp = cast(List[Dict[str, str]], resp)
            return [Package.from_api_response(pkg) for pkg in resp]
        resp = cast(List[str], resp)
        return [Package.from_key(key) for key in resp]

    def repo_search(
        self, name: str, query: str = "", with_deps: bool = False, details: bool = False
    ) -> List[Package]:
        return self._search("local_repo", name, query, with_deps, details)

    def _repo_add_delete_by_key(
        self, method: str, name: str, keys: Sequence[str]
    ) -> Repo:
        url = urljoin(self.url, self.repos_url_path, name, "packages")
        body = {"PackageRefs": keys}
        repo_data = self._request(method, url, data=body)
        repo_data = cast(Dict[str, str], repo_data)
        return Repo.from_api_response(repo_data)

    def repo_add_packages_by_key(self, name: str, keys: Sequence[str]) -> Repo:
        return self._repo_add_delete_by_key("POST", name, keys)

    def repo_delete_packages_by_key(self, name: str, keys: Sequence[str]) -> Repo:
        return self._repo_add_delete_by_key("DELETE", name, keys)

    def snapshot_create_from_repo(
        self, repo_name: str, snapshot_name: str, description: str = None
    ) -> Snapshot:
        """
        Create snapshot from local repo

        Arguments:
            repo_name -- local repo name to snapshot
            snapshot_name -- new snapshot name
            description -- optional human-readable description string
        """
        url = urljoin(self.url, self.repos_url_path, repo_name, "snapshots")
        data = {"Name": snapshot_name}
        if description:
            data["Description"] = description
        snapshot_data = self._request("POST", url, data=data)
        snapshot_data = cast(Dict[str, str], snapshot_data)
        return Snapshot.from_api_response(snapshot_data)

    def snapshot_create_from_package_keys(
        self,
        name: str,
        keys: Sequence[str],
        source_snapshots: Sequence[str] = (),
        description: str = None,
    ) -> Snapshot:
        """
        Create snapshot from a list of packages keys

        Arguments:
            name -- new snapshot name
            keys -- list of package keys to be included in new snapshot
            source_snapshots -- list of source snapshot names (only for tracking purposes)
            description -- optional human-readable description string
        """
        url = urljoin(self.url, self.snapshots_url_path)
        data = {"Name": name, "PackageRefs": keys}
        if description:
            data["Description"] = description
        if source_snapshots:
            data["SourceSnapshots"] = source_snapshots
        snapshot_data = self._request("POST", url, data=data)
        snapshot_data = cast(Dict[str, str], snapshot_data)
        return Snapshot.from_api_response(snapshot_data)

    def snapshot_show(self, name: str) -> Snapshot:
        """
        Returns Snapshot representing snapshot 'name'

        Arguments:
            name -- snapshot name
        """
        url = urljoin(self.url, self.snapshots_url_path, name)
        snap_data = self._request("GET", url)
        snap_data = cast(Dict[str, str], snap_data)
        return Snapshot.from_api_response(snap_data)

    def snapshot_list(self) -> List[Snapshot]:
        """Return a list of all snapshots"""
        snap_list = self._request("GET", urljoin(self.url, self.snapshots_url_path))
        snap_list = cast(List[Dict[str, str]], snap_list)
        return [Snapshot.from_api_response(snap) for snap in snap_list]

    def snapshot_edit(
        self, name: str, new_name: str = "", new_description: str = ""
    ) -> Snapshot:
        """
        Modifies snapshot named 'name'

        Arguments:
            name -- snapshot name
            new_name -- rename snapshot to this name
            new_description -- set description to this
        """
        body = {}  # type: Dict[str, str]
        if new_name:
            body["Name"] = new_name
        if new_description:
            body["Description"] = new_description
        url = urljoin(self.url, self.snapshots_url_path, name)
        snap_data = self._request("PUT", url, body)
        snap_data = cast(Dict[str, str], snap_data)
        return Snapshot.from_api_response(snap_data)

    def snapshot_search(
        self, name: str, query: str = "", with_deps: bool = False, details: bool = False
    ) -> List[Package]:
        return self._search("snapshot", name, query, with_deps, details)

    def snapshot_delete(self, name: str, force: bool = False) -> None:
        """
        Delete snapshot named 'name'

        Arguments:
            name -- snapshot name
            force -- delete snapshot even if it's pointed by another snapshots
        """
        url = urljoin(self.url, self.snapshots_url_path, name)
        params = {}  # type: Dict[str, str]
        if force:
            params["force"] = "1"
        self._request("DELETE", url, params=params)

    def snapshot_diff(
        self, snap1_name: str, snap2_name: str
    ) -> List[Tuple[Optional[Package], Optional[Package]]]:
        """
        Show diff between 2 snapshots

        Arguments:
            snap1_name, snap2_name -- names of snapshots to show diff of
        """
        url = urljoin(self.url, self.snapshots_url_path, snap1_name, "diff", snap2_name)
        diff_data = self._request("GET", url)
        diff_data = cast(List[Dict[str, Optional[str]]], diff_data)
        out = []
        for line in diff_data:
            left = Package.from_key(line["Left"]) if line["Left"] else None
            right = Package.from_key(line["Right"]) if line["Right"] else None
            out.append((left, right))
        return out

    def publish_create(
        self,
        source_kind: str,
        sources: Iterable[Source],
        storage: str = "",
        prefix: str = "",
        distribution: str = "",
        architectures: Iterable[str] = (),
        label: str = "",
        origin: str = "",
        not_automatic: bool = False,
        but_automatic_upgrades: bool = False,
        acquire_by_hash: bool = False,
        force_overwrite: bool = False,
        skip_cleanup: bool = False,
    ) -> Publish:
        publish = Publish(
            source_kind=source_kind,
            sources=sources,
            storage=storage,
            prefix=prefix,
            distribution=distribution,
            architectures=architectures,
            label=label,
            origin=origin,
            not_automatic=not_automatic,
            but_automatic_upgrades=but_automatic_upgrades,
            acquire_by_hash=acquire_by_hash,
        )
        body = publish.api_params
        body["Signing"] = self.get_signing_config(
            publish.full_prefix, publish.distribution
        ).kwargs

        url = urljoin(self.url, self.publish_url_path)
        if publish.full_prefix != ".":
            url = urljoin(url, publish.full_prefix_escaped)

        if force_overwrite:
            body["ForceOverwrite"] = force_overwrite
        if skip_cleanup:
            body["SkipCleanup"] = skip_cleanup

        pub_data = self._request("POST", url, body)
        pub_data = cast(Dict[str, Any], pub_data)
        return Publish.from_api_response(pub_data)

    def publish_list(self) -> List[Publish]:
        url = urljoin(self.url, self.publish_url_path)
        pub_list = self._request("GET", url)
        pub_list = cast(List[Dict[str, Any]], pub_list)
        return [Publish.from_api_response(p) for p in pub_list]

    def publish_drop(
        self,
        publish: Publish = None,
        storage: str = "",
        prefix: str = "",
        distribution: str = "",
        force: bool = False,
    ) -> None:
        if publish:
            pub = publish
        else:
            pub = Publish(
                source_kind="local",
                sources=[],
                storage=storage,
                prefix=prefix,
                distribution=distribution,
            )
        url = urljoin(
            self.url, self.publish_url_path, pub.full_prefix_escaped, pub.distribution
        )
        self._request("DELETE", url)

    def publish_update(
        self,
        publish: Publish = None,
        force_overwrite: bool = False,
        *,
        storage: str = "",
        prefix: str = "",
        distribution: str = "",
        snapshots: Iterable[Source] = (),
        acquire_by_hash: bool = False,
    ) -> Publish:
        if not publish:
            if snapshots:
                publish = Publish(
                    source_kind="snapshot",
                    sources=snapshots,
                    storage=storage,
                    prefix=prefix,
                    distribution=distribution,
                    acquire_by_hash=acquire_by_hash,
                )
            else:
                publish = Publish(
                    source_kind="local",
                    sources=[],
                    storage=storage,
                    prefix=prefix,
                    distribution=distribution,
                    acquire_by_hash=acquire_by_hash,
                )
        body = {}  # type: Dict[str, Any]
        body["Signing"] = self.get_signing_config(
            publish.full_prefix, publish.distribution
        ).kwargs
        if publish.acquire_by_hash:
            body["AcquireByHash"] = publish.acquire_by_hash
        if force_overwrite:
            body["ForceOverwrite"] = force_overwrite
        if publish.source_kind == "snapshot":
            body["Snapshots"] = publish.sources_dict

        url = urljoin(
            self.url,
            self.publish_url_path,
            publish.full_prefix_escaped,
            publish.distribution,
        )
        pub_data = self._request("PUT", url, body)
        pub_data = cast(Dict[str, Any], pub_data)
        return Publish.from_api_response(pub_data)

    def package_show(self, key: str) -> Package:
        pkg_data = self._request("GET", urljoin(self.url, self.packages_url_path, key))
        pkg_data = cast(Dict[str, str], pkg_data)
        return Package.from_api_response(pkg_data)

    def version(self) -> str:
        version_data = self._request("GET", urljoin(self.url, "api/version"))
        version_data = cast(Dict[str, str], version_data)
        return version_data["Version"]


def search(
    aptly: Client,
    queries: Iterable[str] = ("",),
    with_deps: bool = False,
    details: bool = False,
    max_workers: int = 5,
    store_filter: re.Pattern = None,
) -> Tuple[List[Tuple[Union[Repo, Snapshot], List[Package]]], List[AptlyApiError]]:
    repos = aptly.repo_list()
    snapshots = aptly.snapshot_list()
    stores = repos + snapshots
    if store_filter:
        stores = filter(lambda s: store_filter.search(s.name), stores)
    tasks = [(store, query) for store in stores for query in queries]

    def worker(
        store: Union[Repo, Snapshot], query: str
    ) -> Tuple[Union[Repo, Snapshot], List[Package]]:
        if isinstance(store, Repo):
            return store, aptly.repo_search(store.name, query, with_deps, details)
        if isinstance(store, Snapshot):
            return store, aptly.snapshot_search(store.name, query, with_deps, details)
        raise TypeError("Invalid store type of {}: {}".format(store, type(store)))

    futures = []
    result = []
    errors = []
    with ThreadPoolExecutor(max_workers=max_workers) as exe:
        try:
            for task in tasks:
                futures.append(exe.submit(worker, *task))
            for future in as_completed(futures, 300):
                try:
                    store, packages = future.result()
                    if packages:
                        result.append((store, packages))
                except AptlyApiError as exc:
                    errors.append(exc)
        except KeyboardInterrupt:
            log.warning("Received SIGINT. Trying to abort requests...")
            for future in futures:
                future.cancel()
    return result, errors


#    def _search_(
#        self,
#        container: PackageContainer,
#        query: str = None,
#        with_depls: bool = False,
#        details: bool = False,
#    ) -> PackageContainer:
#        """
#        Search packages in PackageContainer (Repo or Snapshot) using query and
#        return PackageContainer instance with 'package' attribute set to search
#        result.
#
#        Arguments:
#            container -- Snapshot or Repo instance
#
#        Keyword arguments:
#            query -- optional search query. By default lists all packages
#            with_depls -- if True, also returns dependencies of packages
#                          matched in query
#            details -- fill in 'fields' attribute of returned Package instances
#
#        Raises RepoNotFoundError or SnapshotNotFoundError if container was not
#        found, and InvalidOperationError if query is invalid.
#        """
#        if isinstance(container, Repo):
#            search_func = self.aptly.repos.search_packages
#        elif isinstance(container, Snapshot):
#            search_func = self.aptly.snapshots.list_packages
#        else:
#            raise TypeError("Unexpected type '{}'".format(type(container)))
#        try:
#            pkgs = search_func(container.name, query, with_depls, details)
#        except AptlyAPIException as exc:
#            emsg = exc.args[0]
#            if exc.status_code == 400 and "parsing failed:" in emsg.lower():
#                _, _, fail_desc = emsg.partition(":")
#                raise InvalidOperationError(
#                    'Bad query "{}":{}'.format(query, fail_desc)
#                )
#            if exc.status_code == 404:
#                if isinstance(container, Repo):
#                    raise RepoNotFoundError(container.name)
#                if isinstance(container, Snapshot):
#                    raise SnapshotNotFoundError(container.name)
#            raise
#        return container._replace(
#            packages=frozenset(Package.from_aptly_api(pkg) for pkg in pkgs)
#        )
#
#    def search(
#        self,
#        targets: Sequence[PackageContainers],
#        queries: Union[Sequence[str], Sequence[None]] = None,
#        with_deps: bool = False,
#        details: bool = False,
#    ) -> Tuple[List[PackageContainers], List[Exception]]:
#        """
#        Search list of queries in aptly local repos and snapshots in parallel
#        and return tuple of PackageContainers list with found packages and list of
#        exceptions encountered during search
#
#        Keyword arguments:
#            targets -- PackageContainers (Snapshots and Repos) instances
#            queries -- list of search queries. By default lists all packages
#            with_depls -- return dependencies of packages matched in query
#            details -- fill in 'fields' attribute of returned Package instances
#        """
#        queries = queries[:] if queries else [None]
#        results = {}  # type: Dict[PackageContainers, set]
#        futures = []
#        errors = []
#        with ThreadPoolExecutor(max_workers=self.max_workers) as exe:
#            try:
#                for target, query in product(targets, queries):
#                    futures.append(
#                        exe.submit(self._search_, target, query, with_deps, details)
#                    )
#                for future in as_completed(futures, 300):
#                    try:
#                        container = future.result()  # type: PackageContainers
#                        if container.packages:
#                            key = container._replace(packages=frozenset())
#                            results.setdefault(key, set()).update(container.packages)
#                    except Exception as exc:
#                        errors.append(exc)
#            except KeyboardInterrupt:
#                # NOTE we cannot cancel requests that are hanging on open()
#                # so thread pool's context manager will hang on shutdown()
#                # untill these requests timeout. Timeout is set in aptly client
#                # class constructor and defaults to 60 seconds
#                # Second SIGINT crushes everything though
#                log.warning("Received SIGINT. Trying to abort requests...")
#                for future in futures:
#                    future.cancel()
#                raise
#        result = []
#        for container, pkgs in results.items():
#            result.append(container._replace(packages=frozenset(pkgs)))
#        return result, errors
#
#    def put(
#        self,
#        local_repos: Iterable[str],
#        packages: Iterable[str],
#        force_replace: bool = False,
#    ) -> Tuple[List[Repo], List[Repo], List[Exception]]:
#        """
#        Upload packages from local filesystem to aptly server,
#        put them into local_repos
#
#        Arguments:
#            local_repos -- list of names of local repos to put packages in
#            packages -- list of package file names to upload
#
#        Keyworad arguments:
#            force_replace -- when True remove packages conflicting with package being added
#
#        Returns: tuple (added, failed, errors), where
#            added -- list of instances of aptly_ctl.types.Repo with
#                packages attribute set to frozenset of aptly_ctl.types.Package
#                instances that were successfully added to a local repo
#            failed -- list of instances of aptly_ctl.types.Repo with
#                packages attribute set to frozenset of aptly_ctl.types.Package
#                instances that were not added to a local repo
#            errors -- list of exceptions raised during packages addition
#        """
#        timestamp = datetime.utcnow().timestamp()
#        # os.getpid just in case 2 instances launched at the same time
#        directory = "aptly_ctl_put_{:.0f}_{}".format(timestamp, os.getpid())
#        repos_to_put = [self.repo_show(name) for name in set(local_repos)]
#
#        try:
#            pkgs = tuple(Package.from_file(pkg) for pkg in packages)
#        except OSError as exc:
#            raise AptlyCtlError("Failed to load package: {}".format(exc))
#
#        def worker(
#            repo: Repo, pkgs: Iterable[Package], directory: str, force_replace: bool
#        ) -> Tuple[Repo, Repo]:
#            addition = self.aptly.repos.add_uploaded_file(
#                repo.name,
#                directory,
#                remove_processed_files=False,
#                force_replace=force_replace,
#            )
#            for file in addition.failed_files:
#                log.warning("Failed to add file %s to repo %s", file, repo.name)
#            for msg in addition.report["Warnings"] + addition.report["Removed"]:
#                log.warning(msg)
#            # example Added msg "python3-wheel_0.30.0-0.2_all added"
#            added = [p.split()[0] for p in addition.report["Added"]]
#            added_pkgs, failed_pkgs = [], []
#            for pkg in pkgs:
#                try:
#                    added.remove(pkg.dir_ref)
#                except ValueError:
#                    failed_pkgs.append(pkg)
#                else:
#                    added_pkgs.append(pkg)
#            if added:
#                log.warning(
#                    "Output is incomplete! These packages %s %s",
#                    added,
#                    "were added but omitted in output",
#                )
#            return (
#                repo._replace(packages=frozenset(added_pkgs)),
#                repo._replace(packages=frozenset(failed_pkgs)),
#            )
#
#        log.info('Uploading the packages to directory "%s"', directory)
#        futures, added, failed, errors = [], [], [], []
#        try:
#            self.aptly.files.upload(directory, *packages)
#            with ThreadPoolExecutor(max_workers=self.max_workers) as exe:
#                try:
#                    for repo in repos_to_put:
#                        futures.append(
#                            exe.submit(worker, repo, pkgs, directory, force_replace)
#                        )
#                    for future in as_completed(futures, 300):
#                        try:
#                            result = future.result()
#                            if result[0].packages:
#                                added.append(result[0])
#                            if result[1].packages:
#                                failed.append(result[1])
#                        except Exception as exc:
#                            errors.append(exc)
#                except KeyboardInterrupt:
#                    # NOTE we cannot cancel requests that are hanging on open()
#                    # so thread pool's context manager will hang on shutdown()
#                    # untill these requests timeout. Timeout is set in aptly client
#                    # class constructor and defaults to 60 seconds
#                    # Second SIGINT crushes everything though
#                    log.warning("Received SIGINT. Trying to abort requests...")
#                    for future in futures:
#                        future.cancel()
#                    raise
#        finally:
#            log.info("Deleting directory %s", directory)
#            self.aptly.files.delete(path=directory)
#
#        return (added, failed, errors)
#
#    def remove(self, *repos: Repo) -> List[Tuple[Repo, RepoNotFoundError]]:
#        """
#        Deletes packages from local repo
#
#        Arguments:
#            *repos -- aptly_ctl.types.Repo instances where packages from
#                     'packages' field are to be deleted
#
#        Returns list of tuples for every repo for which package removal failed.
#        The first item in a tuple is an aptly_ctl.types.Repo and the second is
#        exception with description of failure
#        """
#        fails = []
#        for repo in repos:
#            if not repo.packages:
#                continue
#            try:
#                self.aptly.repos.delete_packages_by_key(
#                    repo.name, *[pkg.key for pkg in repo.packages]
#                )
#            except AptlyAPIException as exc:
#                if exc.status_code == 404:
#                    fails.append((repo, RepoNotFoundError(repo.name)))
#                else:
#                    raise
#        return fails
