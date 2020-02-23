import logging
import re
import os
import urllib3  # type: ignore
import json
from collections import OrderedDict
import hashlib
import fnvhash  # type: ignore
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from itertools import product
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
    FrozenSet,
    TypeVar,
    cast,
)
import aptly_api  # type: ignore
from aptly_api import Client, AptlyAPIException
from aptly_ctl.exceptions import (
    AptlyCtlError,
    RepoNotFoundError,
    InvalidOperationError,
    SnapshotNotFoundError,
    AptlyApiError,
)

from aptly_ctl.debian import Version, get_control_file_fields
from aptly_ctl.util import urljoin, timedelta_pretty

logger = logging.getLogger(__name__)

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
    """Represents package in aptly or on local filesystem"""

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
    def from_aptly_api(cls, package: aptly_api.Package) -> "Package":
        """Create from instance of aptly_api.Package"""
        parsed_key = KEY_REGEXP.match(package.key)
        if parsed_key is None:
            raise ValueError("Invalid package: {}".format(package))
        prefix, arch, name, _, files_hash = parsed_key.groups()
        version = Version(parsed_key.group(4))
        fields = None
        if package.fields:
            fields = OrderedDict(sorted(package.fields.items()))
        return cls(
            name=name,
            version=version,
            arch=arch,
            prefix=prefix,
            files_hash=files_hash,
            fields=fields,
        )

    @classmethod
    def from_key(cls, key: str) -> "Package":
        """Create from instance of aptly key"""
        return cls.from_aptly_api(aptly_api.Package(key, None, None, None))

    @classmethod
    def from_file(cls, filepath: str) -> "Package":
        """
        Build representation of aptly package from package on local filesystem
        """
        hashes = [hashlib.md5(), hashlib.sha1(), hashlib.sha256()]
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
        return cls(
            name=name,
            version=version,
            arch=arch,
            prefix="",
            files_hash=files_hash,
            fields=None,
            file=fileinfo,
        )


class Repo(NamedTuple):
    """Represents local repo in aptly"""

    name: str
    comment: str = ""
    default_distribution: str = ""
    default_component: str = ""
    packages: FrozenSet[Package] = frozenset()

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

    @classmethod
    def from_aptly_api(
        cls, repo: aptly_api.Repo, packages: FrozenSet[Package] = frozenset()
    ) -> "Repo":
        """Create from instance of aply_api.Repo"""
        return cls(
            name=repo.name,
            comment=repo.comment if repo.comment else None,
            default_distribution=repo.default_distribution
            if repo.default_distribution
            else None,
            default_component=repo.default_component
            if repo.default_component
            else None,
            packages=packages,
        )


class Snapshot(NamedTuple):
    """Represents snapshot in aptly"""

    name: str
    description: str = ""
    created_at: Optional[datetime] = None
    packages: FrozenSet[Package] = frozenset()

    @classmethod
    def from_aptly_api(
        cls, snapshot: aptly_api.Snapshot, packages: FrozenSet[Package] = frozenset(),
    ) -> "Snapshot":
        """Create from instance of aply_api.Snapshot"""
        return cls(
            name=snapshot.name,
            description=snapshot.description,
            created_at=snapshot.created_at,
            packages=packages,
        )


PackageContainer = TypeVar("PackageContainer", Repo, Snapshot)
PackageContainers = Union[Repo, Snapshot]


class Source(NamedTuple):
    """Represents source from which publishes are created"""

    container: PackageContainers
    component: Optional[str] = None


class Publish(NamedTuple):
    """Represents publish in aptly"""

    source_kind: str
    sources: FrozenSet[Source]
    storage: str = ""
    prefix: str = ""
    distribution: str = ""
    architectures: Sequence[str] = ()
    label: str = ""
    origin: str = ""
    not_automatic: bool = False
    but_automatic_upgrades: bool = False
    acquire_by_hash: bool = False

    @classmethod
    def new(
        cls,
        sources: Sequence[Source],
        storage: str = "",
        prefix: str = "",
        distribution: str = "",
        architectures: Sequence[str] = (),
        label: str = "",
        origin: str = "",
        not_automatic: bool = False,
        but_automatic_upgrades: bool = False,
        acquire_by_hash: bool = False,
    ) -> "Publish":
        """
        Constructor of Publish that checks input arguments, sets source_kind automatically
        and converts sources to frozenset if necessary.
        This is a prefered way to create Publish instances.
        """
        if not sources:
            raise ValueError("Cannot publish from empty list of sources")

        source_kind = ""
        for source in sources:
            if isinstance(source.container, Repo):
                if source_kind == "":
                    source_kind = "local"
                elif source_kind != "local":
                    raise ValueError(
                        "Unexpected Repo instance '{}' for source_kind='{}'".format(
                            source.container, source_kind
                        )
                    )
            elif isinstance(source.container, Snapshot):
                if source_kind == "":
                    source_kind = "snapshot"
                elif source_kind != "snapshot":
                    raise ValueError(
                        "Unexpected Snapshot instance '{}' for source_kind='{}'".format(
                            source.container, source_kind
                        )
                    )
            else:
                raise ValueError(
                    "Unexpected source '{}' of type '{}'".format(
                        source.container, type(source.container)
                    )
                )

        sources_set = frozenset(sources)

        if prefix and not storage and ":" in prefix:
            raise ValueError(
                "Publish prefix must not contain ':' when storage is not supplied"
            )

        return cls(
            source_kind=source_kind,
            sources=sources_set,
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

    @classmethod
    def from_api_response(cls, resp: Dict[str, Any]) -> "Publish":
        """Create publish instance from API json response"""
        kwargs = {"source_kind": resp["SourceKind"]}
        sources = []
        for source in resp["Sources"]:
            if kwargs["source_kind"] == "local":
                sources.append(Source(Repo(name=source["Name"]), source["Component"]))
            else:
                sources.append(
                    Source(Snapshot(name=source["Name"]), source["Component"])
                )
        kwargs["sources"] = frozenset(sources)
        for key, tgt_key in [
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
            s = {"Name": source.container.name}  # type: Dict[str, str]
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


class Aptly:
    """Aptly API client with more convenient commands"""

    files_url_path: ClassVar[str] = "api/files"
    repos_url_path: ClassVar[str] = "api/repos"
    publish_url_path: ClassVar[str] = "api/publish"

    def __init__(
        self,
        url: str,
        max_workers: int = 10,
        default_signing_config: SigningConfig = DefaultSigningConfig,
        signing_config_map: Dict[str, SigningConfig] = None,
    ) -> None:
        self.http = urllib3.PoolManager()
        self.url = url
        self.aptly = Client(url)
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
    ) -> Tuple[Any, int]:
        start = datetime.now()
        if params:
            logger.debug("sending %s %s params: %s", method, url, params)
            resp = self.http.request_encode_url(method, url, fields=params)
        elif files:
            filenames = [
                "{} {} bytes".format(file_tuple[0], len(file_tuple[1]))
                for file_tuple in files.values()
            ]
            logger.debug("sending %s %s files: %s", method, url, filenames)
            resp = self.http.request_encode_body(method, url, fields=files)
        else:
            encoded_data = json.dumps(data).encode("utf-8") if data else None
            logger.debug("sending %s %s data: %s", method, url, encoded_data)
            resp = self.http.request(
                method,
                url,
                body=encoded_data,
                headers={"Content-Type": "application/json"},
            )
        logger.debug(
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
        return resp_data, resp.status

    def files_upload(self, files: Sequence[str], directory: str) -> List[str]:
        url = urljoin(self.url, self.files_url_path, directory)
        fields = {}  # type: Dict[str, Tuple[str, bytes]]
        for fpath in files:
            filename = os.path.basename(fpath)
            with open(fpath, "br") as f:
                fields[filename] = (filename, f.read())
        resp, _ = self._request("POST", url, files=fields)
        return cast(List[str], resp)

    def files_list(self, directory: str) -> List[str]:
        url = urljoin(self.url, self.files_url_path, directory)
        resp, _ = self._request("GET", url)
        return cast(List[str], resp)

    def files_list_dirs(self) -> List[str]:
        resp, _ = self._request("GET", urljoin(self.url, self.files_url_path))
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
        repo_data, _ = self._request("POST", url, body)
        repo_data = cast(Dict[str, str], repo_data)
        return Repo.from_api_response(repo_data)

    def repo_show(self, name: str) -> Repo:
        """
        Get info about local repo

        Arguments:
            name -- local repo name
        """
        url = urljoin(self.url, self.repos_url_path, name)
        repo_data, _ = self._request("GET", url)
        repo_data = cast(Dict[str, str], repo_data)
        return Repo.from_api_response(repo_data)

    def repo_list(self) -> Sequence[Repo]:
        """Return a list of all the local repos"""
        repo_list, _ = self._request("GET", urljoin(self.url, self.repos_url_path))
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
        repo_data, _ = self._request("PUT", url, body)
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

    def snapshot_show(self, name: str) -> Snapshot:
        """
        Returns aptly_ctl.types.Snapshot representing snapshot 'name' or
        raises AtplyCtlError if such snapshot does not exist

        Arguments:
            name -- snapshot name
        """
        try:
            snapshot = self.aptly.snapshots.show(name)
        except AptlyAPIException as exc:
            if exc.status_code == 404:
                raise SnapshotNotFoundError(name)
            raise
        else:
            return Snapshot.from_aptly_api(snapshot)

    def snapshot_list(self) -> Tuple[Snapshot, ...]:
        """Returns all snapshots as tuple of aptly_ctl.types.Snapshot"""
        return tuple(map(Snapshot.from_aptly_api, self.aptly.snapshots.list()))

    def snapshot_create_from_repo(
        self, repo_name: str, snapshot_name: str, description: str = None
    ) -> Snapshot:
        """
        Create snapshot from local repo

        Arguments:
            repo_name -- local repo name to snapshot
            snapshot_name -- new snapshot name

        Keyword arguments:
            description -- optional human-readable description string
        """
        try:
            snapshot = self.aptly.snapshots.create_from_repo(
                repo_name, snapshot_name, description
            )
        except AptlyAPIException as exc:
            # 400 - snapshot already exists
            # 404 - repo with this name not found
            if exc.status_code == 400:
                raise InvalidOperationError(str(exc))
            if exc.status_code == 404:
                raise RepoNotFoundError(repo_name)
            raise
        else:
            logger.info(
                "Created snapshot '%s' from local repo '%s'", snapshot_name, repo_name
            )
            return Snapshot.from_aptly_api(snapshot)

    def snapshot_create_from_snapshots(
        self, name: str, sources: Sequence[Snapshot], description: str = None
    ) -> Snapshot:
        snapshots, errors = self.search(sources)
        if errors:
            raise errors[0]
        snap_names = [snap.name for snap in sources]
        pkg_keys = [pkg.key for snap in snapshots for pkg in snap.packages]
        try:
            snap = self.aptly.snapshots.create_from_packages(
                snapshotname=name,
                description=description,
                source_snapshots=snap_names,
                package_refs=pkg_keys,
            )
        except AptlyAPIException as exc:
            if exc.status_code in [400, 404]:
                raise InvalidOperationError(str(exc))
            raise
        else:
            return Snapshot.from_aptly_api(snap)

    def snapshot_create_from_packages(
        self, name: str, pkgs: Sequence[Package], description: str = None
    ) -> Snapshot:
        pkg_keys = [pkg.key for pkg in pkgs]
        try:
            snap = self.aptly.snapshots.create_from_packages(
                snapshotname=name, description=description, package_refs=pkg_keys,
            )
        except AptlyAPIException as exc:
            if exc.status_code in [400, 404]:
                raise InvalidOperationError(str(exc))
            raise
        else:
            return Snapshot.from_aptly_api(snap)

    def snapshot_edit(
        self, name: str, new_name: str = None, new_description: str = None
    ) -> Snapshot:
        """
        Modifies snapshot named 'name'. Raises AptlyCtlError if there is no
        snapshot named 'name' or no fields to modify were supplied

        Arguments:
            name -- snapshot name

        Keyword arguments:
            new_name -- rename snapshot to this name
            new_description -- set description to this
        """
        try:
            snapshot = self.aptly.snapshots.update(name, new_name, new_description)
        except AptlyAPIException as exc:
            # 0 - at least one of new_name, new_description required
            # 404 - snapshot with this name not found
            # 409 - snapshot with named new_name already exists
            if exc.status_code in [0, 409]:
                raise InvalidOperationError(str(exc))
            if exc.status_code == 404:
                raise RepoNotFoundError(name)
            raise
        else:
            logger.info("Edited snapshot %s: %s", name, snapshot)
            return Snapshot.from_aptly_api(snapshot)

    def snapshot_delete(self, name: str, force: bool = False) -> None:
        """
        Delete snapshot named 'name'. Raises AptlyCtlError if there is no such
        snapshot or when trying to delete snapshot that has references to it
        with force=False

        Arguments:
            name -- snapshot name

        Keyword arguments:
            force -- delete snapshot even if it's referenced
        """
        try:
            self.aptly.snapshots.delete(name, force)
        except AptlyAPIException as exc:
            # 404 - snapshot with this name not found
            # 409 - snapshot can’t be dropped
            if exc.status_code == 404:
                raise SnapshotNotFoundError(name)
            if exc.status_code == 409:
                raise InvalidOperationError(str(exc))
            raise
        else:
            logger.info("Deleted snapshot %s", name)

    def snapshot_diff(
        self, snap1: str, snap2: str
    ) -> List[Tuple[Optional[Package], Optional[Package]]]:
        """
        Show diff between 2 snapshots
        """
        out = []
        for line in self.aptly.snapshots.diff(snap1, snap2):
            left = Package.from_key(line["Left"]) if line["Left"] else None
            right = Package.from_key(line["Right"]) if line["Right"] else None
            out.append((left, right))
        return out

    def _search(
        self,
        container: PackageContainer,
        query: str = None,
        with_depls: bool = False,
        details: bool = False,
    ) -> PackageContainer:
        """
        Search packages in PackageContainer (Repo or Snapshot) using query and
        return PackageContainer instance with 'package' attribute set to search
        result.

        Arguments:
            container -- Snapshot or Repo instance

        Keyword arguments:
            query -- optional search query. By default lists all packages
            with_depls -- if True, also returns dependencies of packages
                          matched in query
            details -- fill in 'fields' attribute of returned Package instances

        Raises RepoNotFoundError or SnapshotNotFoundError if container was not
        found, and InvalidOperationError if query is invalid.
        """
        if isinstance(container, Repo):
            search_func = self.aptly.repos.search_packages
        elif isinstance(container, Snapshot):
            search_func = self.aptly.snapshots.list_packages
        else:
            raise TypeError("Unexpected type '{}'".format(type(container)))
        try:
            pkgs = search_func(container.name, query, with_depls, details)
        except AptlyAPIException as exc:
            emsg = exc.args[0]
            if exc.status_code == 400 and "parsing failed:" in emsg.lower():
                _, _, fail_desc = emsg.partition(":")
                raise InvalidOperationError(
                    'Bad query "{}":{}'.format(query, fail_desc)
                )
            if exc.status_code == 404:
                if isinstance(container, Repo):
                    raise RepoNotFoundError(container.name)
                if isinstance(container, Snapshot):
                    raise SnapshotNotFoundError(container.name)
            raise
        return container._replace(
            packages=frozenset(Package.from_aptly_api(pkg) for pkg in pkgs)
        )

    def search(
        self,
        targets: Sequence[PackageContainers],
        queries: Union[Sequence[str], Sequence[None]] = None,
        with_deps: bool = False,
        details: bool = False,
    ) -> Tuple[List[PackageContainers], List[Exception]]:
        """
        Search list of queries in aptly local repos and snapshots in parallel
        and return tuple of PackageContainers list with found packages and list of
        exceptions encountered during search

        Keyword arguments:
            targets -- PackageContainers (Snapshots and Repos) instances
            queries -- list of search queries. By default lists all packages
            with_depls -- return dependencies of packages matched in query
            details -- fill in 'fields' attribute of returned Package instances
        """
        queries = queries[:] if queries else [None]
        results = {}  # type: Dict[PackageContainers, set]
        futures = []
        errors = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as exe:
            try:
                for target, query in product(targets, queries):
                    futures.append(
                        exe.submit(self._search, target, query, with_deps, details)
                    )
                for future in as_completed(futures, 300):
                    try:
                        container = future.result()  # type: PackageContainers
                        if container.packages:
                            key = container._replace(packages=frozenset())
                            results.setdefault(key, set()).update(container.packages)
                    except Exception as exc:
                        errors.append(exc)
            except KeyboardInterrupt:
                # NOTE we cannot cancel requests that are hanging on open()
                # so thread pool's context manager will hang on shutdown()
                # untill these requests timeout. Timeout is set in aptly client
                # class constructor and defaults to 60 seconds
                # Second SIGINT crushes everything though
                logger.warning("Received SIGINT. Trying to abort requests...")
                for future in futures:
                    future.cancel()
                raise
        result = []
        for container, pkgs in results.items():
            result.append(container._replace(packages=frozenset(pkgs)))
        return result, errors

    def put(
        self,
        local_repos: Iterable[str],
        packages: Iterable[str],
        force_replace: bool = False,
    ) -> Tuple[List[Repo], List[Repo], List[Exception]]:
        """
        Upload packages from local filesystem to aptly server,
        put them into local_repos

        Arguments:
            local_repos -- list of names of local repos to put packages in
            packages -- list of package file names to upload

        Keyworad arguments:
            force_replace -- when True remove packages conflicting with package being added

        Returns: tuple (added, failed, errors), where
            added -- list of instances of aptly_ctl.types.Repo with
                packages attribute set to frozenset of aptly_ctl.types.Package
                instances that were successfully added to a local repo
            failed -- list of instances of aptly_ctl.types.Repo with
                packages attribute set to frozenset of aptly_ctl.types.Package
                instances that were not added to a local repo
            errors -- list of exceptions raised during packages addition
        """
        timestamp = datetime.utcnow().timestamp()
        # os.getpid just in case 2 instances launched at the same time
        directory = "aptly_ctl_put_{:.0f}_{}".format(timestamp, os.getpid())
        repos_to_put = [self.repo_show(name) for name in set(local_repos)]

        try:
            pkgs = tuple(Package.from_file(pkg) for pkg in packages)
        except OSError as exc:
            raise AptlyCtlError("Failed to load package: {}".format(exc))

        def worker(
            repo: Repo, pkgs: Iterable[Package], directory: str, force_replace: bool
        ) -> Tuple[Repo, Repo]:
            addition = self.aptly.repos.add_uploaded_file(
                repo.name,
                directory,
                remove_processed_files=False,
                force_replace=force_replace,
            )
            for file in addition.failed_files:
                logger.warning("Failed to add file %s to repo %s", file, repo.name)
            for msg in addition.report["Warnings"] + addition.report["Removed"]:
                logger.warning(msg)
            # example Added msg "python3-wheel_0.30.0-0.2_all added"
            added = [p.split()[0] for p in addition.report["Added"]]
            added_pkgs, failed_pkgs = [], []
            for pkg in pkgs:
                try:
                    added.remove(pkg.dir_ref)
                except ValueError:
                    failed_pkgs.append(pkg)
                else:
                    added_pkgs.append(pkg)
            if added:
                logger.warning(
                    "Output is incomplete! These packages %s %s",
                    added,
                    "were added but omitted in output",
                )
            return (
                repo._replace(packages=frozenset(added_pkgs)),
                repo._replace(packages=frozenset(failed_pkgs)),
            )

        logger.info('Uploading the packages to directory "%s"', directory)
        futures, added, failed, errors = [], [], [], []
        try:
            self.aptly.files.upload(directory, *packages)
            with ThreadPoolExecutor(max_workers=self.max_workers) as exe:
                try:
                    for repo in repos_to_put:
                        futures.append(
                            exe.submit(worker, repo, pkgs, directory, force_replace)
                        )
                    for future in as_completed(futures, 300):
                        try:
                            result = future.result()
                            if result[0].packages:
                                added.append(result[0])
                            if result[1].packages:
                                failed.append(result[1])
                        except Exception as exc:
                            errors.append(exc)
                except KeyboardInterrupt:
                    # NOTE we cannot cancel requests that are hanging on open()
                    # so thread pool's context manager will hang on shutdown()
                    # untill these requests timeout. Timeout is set in aptly client
                    # class constructor and defaults to 60 seconds
                    # Second SIGINT crushes everything though
                    logger.warning("Received SIGINT. Trying to abort requests...")
                    for future in futures:
                        future.cancel()
                    raise
        finally:
            logger.info("Deleting directory %s", directory)
            self.aptly.files.delete(path=directory)

        return (added, failed, errors)

    def remove(self, *repos: Repo) -> List[Tuple[Repo, RepoNotFoundError]]:
        """
        Deletes packages from local repo

        Arguments:
            *repos -- aptly_ctl.types.Repo instances where packages from
                     'packages' field are to be deleted

        Returns list of tuples for every repo for which package removal failed.
        The first item in a tuple is an aptly_ctl.types.Repo and the second is
        exception with description of failure
        """
        fails = []
        for repo in repos:
            if not repo.packages:
                continue
            try:
                self.aptly.repos.delete_packages_by_key(
                    repo.name, *[pkg.key for pkg in repo.packages]
                )
            except AptlyAPIException as exc:
                if exc.status_code == 404:
                    fails.append((repo, RepoNotFoundError(repo.name)))
                else:
                    raise
        return fails

    def publish_create(
        self,
        publish: Publish,
        force_overwrite: bool = False,
        skip_cleanup: bool = False,
    ) -> Publish:
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

        pub_data, _ = self._request("POST", url, body)
        pub_data = cast(Dict[str, Any], pub_data)
        return Publish.from_api_response(pub_data)

    def publish_list(self) -> Sequence[Publish]:
        url = urljoin(self.url, self.publish_url_path)
        pub_list, _ = self._request("GET", url)
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
            pub = Publish.new(
                [Source(Repo("test"))],
                storage=storage,
                prefix=prefix,
                distribution=distribution,
            )
        url = urljoin(
            self.url, self.publish_url_path, pub.full_prefix_escaped, pub.distribution
        )
        _, _ = self._request("DELETE", url)

    def publish_update(
        self, publish: Publish, force_overwrite: bool = False
    ) -> Publish:
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
        pub_data, _ = self._request("PUT", url, body)
        pub_data = cast(Dict[str, Any], pub_data)
        return Publish.from_api_response(pub_data)
