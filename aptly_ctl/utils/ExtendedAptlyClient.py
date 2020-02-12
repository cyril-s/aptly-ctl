import logging
from aptly_api import Client
from aptly_api.parts.misc import MiscAPISection
from aptly_api.parts.packages import PackageAPISection
from aptly_api.parts.publish import PublishAPISection
from aptly_api.parts.repos import ReposAPISection
from aptly_api.parts.files import FilesAPISection
from aptly_api.parts.snapshots import SnapshotAPISection
from aptly_api.base import AptlyAPIException
from aptly_ctl.utils import PackageRef, PubSpec
from aptly_ctl.exceptions import AptlyCtlError

logger = logging.getLogger(__name__)


class ExtendedAptlyClient(Client):
    def __init__(self, aptly_server_url, timeout=None):
        if not timeout or timeout < 0:
            super().__init__(aptly_server_url)
        else:
            self.aptly_server_url = aptly_server_url
            self.files = FilesAPISection(self.aptly_server_url, timeout=timeout)
            self.misc = MiscAPISection(self.aptly_server_url, timeout=timeout)
            self.packages = PackageAPISection(self.aptly_server_url, timeout=timeout)
            self.publish = PublishAPISection(self.aptly_server_url, timeout=timeout)
            self.repos = ReposAPISection(self.aptly_server_url, timeout=timeout)
            self.snapshots = SnapshotAPISection(self.aptly_server_url, timeout=timeout)

    def lookup_publish_by_repos(self, repos):
        "Find what publishes depend on specified repos"
        publish_list = self.publish.list()
        publishes_from_local_repo = (
            p for p in publish_list if p.source_kind == "local"
        )
        dependent_pubs = []

        try:
            repos_names = [repo.name for repo in repos]
        except AttributeError:
            repos_names = repos

        for p in publishes_from_local_repo:
            for r in repos_names:
                if r in (source["Name"] for source in p.sources):
                    dependent_pubs.append(p)
                    break
        else:
            return dependent_pubs

    def search_by_PackageRef(self, ref, use_ref_repo=True, detailed=True):
        """
        Search for PackageRef in all repos. If use_ref_repo is True, search
        only in repo of PackageRef if it is not None. Returns list of new PackageRefs
        with hash set, and new attr details if detailed is True
        """
        if use_ref_repo and ref.repo:
            repos_list = [ref.repo]
        else:
            repos_list = [r.name for r in self.repos.list()]

        result = []
        for r in repos_list:
            search_result = self.repos.search_packages(r, ref.dir_ref, detailed=True)
            logger.debug(
                'search for "{}" in "{}": {}'.format(ref.dir_ref, r, search_result)
            )
            if len(search_result) > 1:
                raise AptlyCtlError(
                    'Search for direct reference "{}" in repo "{}" '
                    "returned more than 1 result.".format(ref.dir_ref, r)
                )
            elif len(search_result) == 1:
                new_ref = PackageRef(search_result[0].key)
                new_ref.repo = r
                new_ref.details = search_result[0]
                result.append(new_ref)
        else:
            return result

    def update_dependent_publishes(self, repos, config, dry_run=False):
        pubs = self.lookup_publish_by_repos(repos)
        update_exceptions = []
        for p in pubs:
            logger.info(
                'Updating publish with prefix "{}", dist "{}"'.format(
                    p.prefix, p.distribution
                )
            )
            if dry_run:
                continue
            try:
                update_result = self.publish.update(
                    prefix=p.prefix,
                    distribution=p.distribution,
                    **config.get_signing_config(
                        PubSpec(p.distribution, p.prefix)
                    ).as_dict(prefix="sign_")
                )
            except AptlyAPIException as e:
                logger.error(
                    'Can\'t update publish with prefix "{}", dist "{}".'.format(
                        p.prefix, p.distribution
                    )
                )
                update_exceptions.append(e)
                logger.error(e)
                logger.debug("", exc_info=True)
            else:
                logger.debug("API returned: " + str(update_result))
                logger.info(
                    'Updated publish with prefix "{}", dist "{}".'.format(
                        p.prefix, p.distribution
                    )
                )
        return update_exceptions
