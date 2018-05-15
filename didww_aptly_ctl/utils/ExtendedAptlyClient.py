import logging
from aptly_api import Client
from aptly_api.base import AptlyAPIException
from didww_aptly_ctl.utils.PackageRef import PackageRef
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError

logger = logging.getLogger(__name__)

class ExtendedAptlyClient(Client):

    def lookup_publish_by_repos(self, repos):
        "Find what publishes depend on specified repos"
        publish_list = self.publish.list()
        publishes_from_local_repo = [ p for p in publish_list if p.source_kind == "local" ]
        dependent_pubs = []

        try:
            repos_names = [ repo.name for repo in repos ]
        except AttributeError:
            repos_names = repos

        for p in publishes_from_local_repo:
            for r in repos_names:
                if r in [ source["Name"] for source in p.sources ]:
                    dependent_pubs.append(p)
                    break
        else:
            return dependent_pubs


    def search_by_PackageRef(self, ref):
        if ref.repo:
            repos_list = [ ref.repo ]
        else:
            repos_list = [ r.name for r in self.repos.list() ]

        result = []
        for r in repos_list:
            search_result = self.repos.search_packages(r, ref.dir_ref, detailed=True)
            logger.debug('search for "{}" in "{}": {}'.format(ref.dir_ref, r, search_result))
            if len(search_result) > 1:
                raise DidwwAptlyCtlError('Search for direct reference "{}" in repo "{}" '
                    'returned more than 1 result.'.format(ref.dir_ref, r))
            elif len(search_result) == 1:
                new_ref = PackageRef(search_result[0].key, r)
                new_ref.details = search_result[0]
                result.append()
        else:
            return result

