"""This module contains aptly client class and all associated data types"""
import logging
import re
import os
import json
import hashlib
from datetime import datetime
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
    Pattern,
)
import urllib3  # type: ignore # https://github.com/urllib3/urllib3/issues/1897
import fnvhash  # type: ignore
import dateutil.parser
from aptly_ctl.exceptions import AptlyApiError
from aptly_ctl.debian import Version, get_control_file_fields
from aptly_ctl.util import urljoin, timedelta_pretty
from aptly_ctl import VERSION

log = logging.getLogger(__name__)

KEY_REGEXP = re.compile(r"(\w*?)P(\w+) (\S+) (\S+) (\w+)$")
DIR_REF_REGEXP = re.compile(r"(\S+?)_(\S+?)_(\w+)")


class SigningConfig(NamedTuple):
    """
    Holds configuration for publish signing
    """

    skip: bool = False
    batch: bool = True
    gpgkey: Optional[str] = None
    keyring: Optional[str] = None
    secret_keyring: Optional[str] = None
    passphrase: Optional[str] = None
    passphrase_file: Optional[str] = None

    @property
    def kwargs(self) -> Dict[str, Union[str, bool]]:
        """
        Returns dictionary suitable for api request
        """
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
    """
    Holds info about debian package in a local filesystem
    """

    filename: str
    path: str
    origpath: str
    size: int
    md5: str
    sha1: str
    sha256: str


class InvalidPackageKey(Exception):
    """
    Exception that indicates invalid package key
    """

    def __init__(self, key: str) -> None:
        super().__init__(f"Invalid package key '{key}'")


class Package(NamedTuple):
    """Represents package in aptly or in local filesystem"""

    name: str
    version: Version
    arch: str
    prefix: str
    files_hash: str
    fields: Optional[Dict[str, str]] = None

    @property
    def key(self) -> str:
        """Returns aptly key"""
        return f"{self.prefix}P{self.arch} {self.name} {self.version} {self.files_hash}"

    @property
    def dir_ref(self) -> str:
        """Returns aptly dir ref"""
        return f"{self.name}_{self.version}_{self.arch}"

    @classmethod
    def from_key(cls, key: str) -> "Package":
        """Create from instance of aptly key"""
        match = KEY_REGEXP.match(key)
        if not match:
            raise InvalidPackageKey(key)
        prefix, arch, name, version_str, files_hash = match.groups()
        version = Version(version_str)
        return cls(
            name=name, version=version, arch=arch, prefix=prefix, files_hash=files_hash
        )

    @classmethod
    def from_file(cls, filepath: str) -> Tuple["Package", PackageFileInfo]:
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
        version = Version(fields["Version"])
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
        key_fields = [
            "P" + fields["Architecture"],
            fields["Package"],
            str(version),
            files_hash,
        ]
        fields["Filename"] = fileinfo.filename
        fields["FilesHash"] = files_hash
        fields["Key"] = " ".join(key_fields)
        fields["MD5sum"] = hashes[0].hexdigest()
        fields["SHA1"] = hashes[1].hexdigest()
        fields["SHA256"] = hashes[2].hexdigest()
        fields["SHA512"] = hashes[3].hexdigest()
        fields["ShortKey"] = " ".join(key_fields[:-1])
        fields["Size"] = str(size)
        return (
            cls(
                name=fields["Package"],
                version=version,
                arch=fields["Architecture"],
                prefix="",
                files_hash=files_hash,
                fields=fields,
            ),
            fileinfo,
        )

    @classmethod
    def from_api_response(cls, resp: Dict[str, str]) -> "Package":
        """
        Build Package instance from json in api response
        """
        pkg = cls.from_key(resp["Key"])
        return pkg._replace(fields=resp)

    def __hash__(self) -> int:
        # no need to include fields since files_hash calculation involves control file fields
        return hash((self.name, self.version, self.arch, self.prefix, self.files_hash))


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

    def __str__(self) -> str:
        return f"{self.name} ({self.component})"

    def __hash__(self) -> int:
        return hash((self.name, self.component))


class Publish(NamedTuple):
    """Represents publish in aptly"""

    source_kind: str
    sources: Tuple[Source, ...]
    storage: str = ""
    prefix: str = ""
    distribution: str = ""
    architectures: Tuple[str, ...] = ()
    label: str = ""
    origin: str = ""
    not_automatic: bool = False
    but_automatic_upgrades: bool = False
    acquire_by_hash: bool = False

    @classmethod
    def from_api_response(cls, resp: Dict[str, Any]) -> "Publish":
        """Create publish instance from API json response"""
        sources = tuple(
            Source(source["Name"], source.get("Component", None))
            for source in resp["Sources"]
        )
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
        """
        Get Publish sources as list of dictionaries
        """
        sources = []
        for source in self.sources:
            if source.component:
                sources.append({"Name": source.name, "Component": source.component})
            else:
                sources.append({"Name": source.name})
        return sources

    @property
    def api_params(self) -> Dict[str, Any]:
        """
        Return dictionary suitable for api request
        """
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
        """
        Return complete prefix (url path part) for publish
        """
        prefix = self.prefix if self.prefix else "."
        if not self.storage:
            return prefix
        return self.storage + ":" + prefix

    @property
    def full_prefix_escaped(self) -> str:
        """
        Return complete prefix (url path part) for publish escaped according to aptly rules
        """
        prefix = self.full_prefix
        if prefix == ".":
            return ":."
        prefix = prefix.replace("_", "__")
        prefix = prefix.replace("/", "_")
        return prefix

    def __str__(self) -> str:
        return f"{self.full_prefix}/{self.distribution}"

    def __hash__(self) -> int:
        return hash((field for field in self))  # pylint: disable=not-an-iterable


class FilesReport(NamedTuple):
    """
    Represents api response on request to add packages to a local repo
    """

    failed: Sequence[str] = ()
    added: Sequence[str] = ()
    removed: Sequence[str] = ()
    warnings: Sequence[str] = ()


class Client:  # pylint: disable=too-many-public-methods
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
        timeout: urllib3.Timeout = urllib3.Timeout(connect=15.0, read=None),
    ) -> None:
        self.base_headers = {"User-Agent": f"aptly-ctl/{VERSION}"}
        self.http = urllib3.PoolManager(headers=self.base_headers, timeout=timeout)
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
        """
        Get SigningConfig for particular publish
        """
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
                headers=self.base_headers.update({"Content-Type": "application/json"}),
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
        """
        Upload files to aptly server upload dir
        """
        url = urljoin(self.url, self.files_url_path, directory)
        fields = {}  # type: Dict[str, Tuple[str, bytes]]
        for fpath in files:
            filename = os.path.basename(fpath)
            with open(fpath, "br") as f:
                fields[filename] = (filename, f.read())
        resp = self._request("POST", url, files=fields)
        return cast(List[str], resp)

    def files_list(self, directory: str) -> List[str]:
        """
        List files on aptly server upload dir
        """
        url = urljoin(self.url, self.files_url_path, directory)
        resp = self._request("GET", url)
        return cast(List[str], resp)

    def files_list_dirs(self) -> List[str]:
        """
        List dirs in upload dir on aptly server
        """
        resp = self._request("GET", urljoin(self.url, self.files_url_path))
        return cast(List[str], resp)

    def files_delete_dir(self, directory: str) -> None:
        """
        Delete directory on aptly server in upload dir
        """
        url = urljoin(self.url, self.files_url_path, directory)
        self._request("DELETE", url)

    def files_delete_file(self, directory: str, file: str) -> None:
        """
        Delete files in upload dir on aptly server
        """
        url = urljoin(self.url, self.files_url_path, directory, file)
        self._request("DELETE", url)

    def repo_create(
        self,
        repo_name: str,
        comment: str = "",
        default_distribution: str = "",
        default_component: str = "",
    ) -> Repo:
        """
        Creates new local repo

        Arguments:
            repo_name -- local repo name
            comment -- comment for local repo
            default_distribution -- default distribution. When creating publish
                from local repo, this attribute is looked up to determine target
                distribution for publish if it is not supplied explicitly.
            default_component -- default component. When creating publish
                from local repo, this attribute is looked up to determine target
                component for this repo if it is not supplied explicitly.
        """
        body = {"Name": repo_name}
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

    def repo_show(self, repo_name: str) -> Repo:
        """
        Get info about local repo

        Arguments:
            repo_name -- local repo name
        """
        url = urljoin(self.url, self.repos_url_path, repo_name)
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
        repo_name: str,
        comment: str = "",
        default_distribution: str = "",
        default_component: str = "",
    ) -> Repo:
        """
        Edit local repo.

        Arguments:
            repo_name -- local repo name
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
        url = urljoin(self.url, self.repos_url_path, repo_name)
        repo_data = self._request("PUT", url, body)
        repo_data = cast(Dict[str, str], repo_data)
        return Repo.from_api_response(repo_data)

    def repo_delete(self, repo_name: str, force: bool = False) -> None:
        """
        Delete local repo named

        Arguments:
            repo_name -- local repo name
            force -- delete local repo even if it's pointed by a snapshot
        """
        url = urljoin(self.url, self.repos_url_path, repo_name)
        params = {}  # type: Dict[str, str]
        if force:
            params["force"] = "1"
        self._request("DELETE", url, params=params)

    def repo_add_packages(
        self,
        repo_name: str,
        directory: str,
        file: str = "",
        no_remove: bool = False,
        force_replace: bool = False,
    ) -> FilesReport:
        """
        Add packages from upload dir on aptly server to a local repo
        """
        url = urljoin(self.url, self.repos_url_path, repo_name, "file", directory)
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
        store_name: str,
        query: str = "",
        with_deps: bool = False,
        details: bool = False,
    ) -> List[Package]:
        if container == "local_repo":
            url = urljoin(self.url, self.repos_url_path, store_name, "packages")
        elif container == "snapshot":
            url = urljoin(self.url, self.snapshots_url_path, store_name, "packages")
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
        self,
        repo_name: str,
        query: str = "",
        with_deps: bool = False,
        details: bool = False,
    ) -> List[Package]:
        """
        Search packages in a local repo
        """
        return self._search("local_repo", repo_name, query, with_deps, details)

    def _repo_add_delete_by_key(
        self, method: str, repo_name: str, keys: Sequence[str]
    ) -> Repo:
        url = urljoin(self.url, self.repos_url_path, repo_name, "packages")
        body = {"PackageRefs": keys}
        repo_data = self._request(method, url, data=body)
        repo_data = cast(Dict[str, str], repo_data)
        return Repo.from_api_response(repo_data)

    def repo_add_packages_by_key(self, repo_name: str, keys: Sequence[str]) -> Repo:
        """
        Add packages to a local repo by package keys
        """
        return self._repo_add_delete_by_key("POST", repo_name, keys)

    def repo_delete_packages_by_key(self, repo_name: str, keys: Sequence[str]) -> Repo:
        """
        Delete packages from a local repo by package keys
        """
        return self._repo_add_delete_by_key("DELETE", repo_name, keys)

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
        snap_name: str,
        keys: Sequence[str],
        source_snapshots: Sequence[str] = (),
        description: str = None,
    ) -> Snapshot:
        """
        Create snapshot from a list of packages keys

        Arguments:
            snap_name -- new snapshot name
            keys -- list of package keys to be included in new snapshot
            source_snapshots -- list of source snapshot names (only for tracking purposes)
            description -- optional human-readable description string
        """
        url = urljoin(self.url, self.snapshots_url_path)
        data = {"Name": snap_name, "PackageRefs": keys}
        if description:
            data["Description"] = description
        if source_snapshots:
            data["SourceSnapshots"] = source_snapshots
        snapshot_data = self._request("POST", url, data=data)
        snapshot_data = cast(Dict[str, str], snapshot_data)
        return Snapshot.from_api_response(snapshot_data)

    def snapshot_show(self, snap_name: str) -> Snapshot:
        """
        Returns Snapshot representing snapshot 'name'

        Arguments:
            snap_name -- snapshot name
        """
        url = urljoin(self.url, self.snapshots_url_path, snap_name)
        snap_data = self._request("GET", url)
        snap_data = cast(Dict[str, str], snap_data)
        return Snapshot.from_api_response(snap_data)

    def snapshot_list(self) -> List[Snapshot]:
        """Return a list of all snapshots"""
        snap_list = self._request("GET", urljoin(self.url, self.snapshots_url_path))
        snap_list = cast(List[Dict[str, str]], snap_list)
        return [Snapshot.from_api_response(snap) for snap in snap_list]

    def snapshot_edit(
        self, snap_name: str, new_name: str = "", new_description: str = ""
    ) -> Snapshot:
        """
        Modifies snapshot named 'snap_name'

        Arguments:
            snap_name -- snapshot name
            new_name -- rename snapshot to this name
            new_description -- set description to this
        """
        body = {}  # type: Dict[str, str]
        if new_name:
            body["Name"] = new_name
        if new_description:
            body["Description"] = new_description
        url = urljoin(self.url, self.snapshots_url_path, snap_name)
        snap_data = self._request("PUT", url, body)
        snap_data = cast(Dict[str, str], snap_data)
        return Snapshot.from_api_response(snap_data)

    def snapshot_search(
        self,
        snap_name: str,
        query: str = "",
        with_deps: bool = False,
        details: bool = False,
    ) -> List[Package]:
        """
        Search packages in a snapshot
        """
        return self._search("snapshot", snap_name, query, with_deps, details)

    def snapshot_delete(self, snap_name: str, force: bool = False) -> None:
        """
        Delete snapshot named 'name'

        Arguments:
            snap_name -- snapshot name
            force -- delete snapshot even if it's pointed by another snapshots
        """
        url = urljoin(self.url, self.snapshots_url_path, snap_name)
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

    def publish_create(  # pylint: disable=too-many-arguments
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
        """
        Create publish either from local repos or from snapshots

        Arguments:
            source_kind -- "local" to create from local repos
                            and "snapshot" to create from snapshots
            sources -- Interable of Sources instances from which publish is created
            storage -- optional storage type for publish. Default is local filesystem,
                        "s3" for S3 "swift" for Swift
            prefix -- optional url part that goes right after aply publish root
            distribution -- debian distribution of created publish. Guessed from sources by default
            architectures -- list of architectures in created publish
            label, origin -- values of corresponing fields in published repository stanza
            not_automatic -- indicates to the package manager to not install or upgrade packages
                             from the repository without user consent
            but_automatic_upgrades -- excludes upgrades from the not_automic setting
            acquire_by_hash -- provide index files by hash
            force_overwrite -- when publishing, overwrite files in pool/ directory without notice
            skip_cleanup -- don’t remove unreferenced files in prefix/component
        """
        publish = Publish(
            source_kind=source_kind,
            sources=tuple(sources),
            storage=storage,
            prefix=prefix,
            distribution=distribution,
            architectures=tuple(architectures),
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
        """
        Get a list of publishes
        """
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
        """
        Delete publish
        """
        if publish:
            pub = publish
        else:
            pub = Publish(
                source_kind="local",
                sources=tuple(),
                storage=storage,
                prefix=prefix,
                distribution=distribution,
            )
        url = urljoin(
            self.url, self.publish_url_path, pub.full_prefix_escaped, pub.distribution
        )
        params = {"force": "1"} if force else {}
        self._request("DELETE", url, params=params)

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
        """
        Update publish pulling new packages from local repos
        or switching to new snapshots
        """
        if not publish:
            if snapshots:
                publish = Publish(
                    source_kind="snapshot",
                    sources=tuple(snapshots),
                    storage=storage,
                    prefix=prefix,
                    distribution=distribution,
                    acquire_by_hash=acquire_by_hash,
                )
            else:
                publish = Publish(
                    source_kind="local",
                    sources=tuple(),
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
        """
        Get full package info
        """
        pkg_data = self._request("GET", urljoin(self.url, self.packages_url_path, key))
        pkg_data = cast(Dict[str, str], pkg_data)
        return Package.from_api_response(pkg_data)

    def version(self) -> str:
        """
        Get aptly server version
        """
        version_data = self._request("GET", urljoin(self.url, "api/version"))
        version_data = cast(Dict[str, str], version_data)
        return version_data["Version"]


def search(  # pylint: disable=too-many-locals
    aptly: Client,
    queries: Iterable[str] = ("",),
    with_deps: bool = False,
    details: bool = False,
    max_workers: int = 5,
    store_filter: Pattern = None,
    search_snapshots: bool = True,
) -> Tuple[List[Tuple[Union[Repo, Snapshot], List[Package]]], List[AptlyApiError]]:
    """
    Search all queries in aptly local repos and snapshots in parallel
    and return tuple of results list and errors list. Result list contyains tuples
    with Repo or Snapshot as first item and a list of Package(s) found in them as the second.
    List of erros is a list of exception encountered during the search.

    Keyword arguments:
        queries -- list of search queries and/or package keys. By default lists all packages
        with_deps -- return dependencies of packages matched in query
        details -- fill in 'fields' attribute of returned Package instances
        max_workers -- max number of threads
        store_filter -- regex to filter Repo and Snapshot instances by name
        search_snapshots -- search snapshots as well, True by default
    """
    repos = aptly.repo_list()
    snapshots = aptly.snapshot_list() if search_snapshots else []
    if store_filter:
        repos = [repo for repo in repos if store_filter.search(repo.name)]
        snapshots = [snap for snap in snapshots if store_filter.search(snap.name)]

    def worker(
        store: Union[Repo, Snapshot], is_local_repo: bool, query: str
    ) -> Tuple[Union[Repo, Snapshot], List[Package]]:
        pkg = None
        try:
            pkg = Package.from_key(query)
            query = pkg.dir_ref
        except InvalidPackageKey:
            pass

        if is_local_repo:
            pkgs = aptly.repo_search(store.name, query, with_deps, details)
        else:
            pkgs = aptly.snapshot_search(store.name, query, with_deps, details)

        if pkg:
            pkgs = [p for p in pkgs if p.files_hash == pkg.files_hash]

        return store, pkgs

    futures = []
    result = []
    errors = []
    with ThreadPoolExecutor(max_workers=max_workers) as exe:
        try:
            for query in queries:
                for repo in repos:
                    futures.append(exe.submit(worker, repo, True, query))
                for snap in snapshots:
                    futures.append(exe.submit(worker, snap, False, query))
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
