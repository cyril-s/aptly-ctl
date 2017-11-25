import logging
from re import match
import requests
from aptly_api.base import AptlyAPIException
from aptly_api.parts.publish import PublishAPISection
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError

aptly_key_regex = r"P(\w+) ([\w-]+) ([\w~.-]+) (\w+)$"
direct_reference_regex = r"([\w-]+)_([\w~.-]+)_(\w+)$"
logger = logging.getLogger(__name__)

def aptly_key_to_direct_reference(key):
    """
    Converts aptly key ("Pamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c") 
    to direct reference ("didww-billing_2.2.0~rc5_amd64").
    Returns tuple (direct_reference, hash)
    """
    m = match(aptly_key_regex, key)
    if not m or len(m.groups()) != 4:
        raise ValueError('Incorrect aptly key "%s"' % key)

    dir_ref = "_".join([m.group(2), m.group(3), m.group(1)])
    return (dir_ref, m.group(4))


def direct_reference_to_aptly_key(client, repo, dir_ref):
    """
    Searches repo for package specified by direct referece and returns its key.
    Returns None if cannot find. Raise RuntimeError if obtained multiple results.
    Uses aptly-api-client client.
    """
    if not match(direct_reference_regex, dir_ref):
        raise ValueError('Incorrect direct reference "%s"' % dir_ref)

    search_result = client.repos.search_packages(repo, dir_ref)
    if len(search_result) == 0:
        key = None
    elif len(search_result) == 1:
        key = search_result[0][0]
    else:
        keys = [ k[0] for k in search_result ]
        raise DidwwAptlyCtlError("Search by direct reference {} returned many results: {}".format(dir_ref, keys), logger=logger)

    return key


def manual_publish_update(url, prefix, distribution, pass_file):
    full_url = "{0}/publish/{1}/{2}".format(url, prefix, distribution)
    data = dict()
    data["Signing"] = dict()
    data["Signing"]["PassphraseFile"] = pass_file
    # To get 500 uncomment this
    #data["Signing"]["GpgKey"] = "/home/pkg/didww.pgp"

    r = requests.put(full_url, json=data)
    r.raise_for_status()

    return PublishAPISection.endpoint_from_response(r.json())


def publish_update(client, prefix, distribution, pass_file):
    """
    aptly_api 0.1.5 throws exception when sign_gpgkey is not passed.
    But it is ok because aplty polls gpg agent for key from keyring.
    This function is a wrapper that takes care of this case.
    """
    update_result = None
    try:
        update_result = client.publish.update(
                prefix=prefix,
                distribution=distribution,
                sign_passphrase_file=pass_file)
    except AptlyAPIException as e:
        if not e.args[0] == "Update needs a gpgkey to sign with if sign_skip is False":
            raise
        else:
            try:
                update_result = manual_publish_update(
                        client.aptly_server_url,
                        prefix, distribution,
                        pass_file)
            except requests.exceptions.HTTPError as e:
                err_data = e.response.json()
                raise DidwwAptlyCtlError(
                        "Failed to update publish %s/%s manually: %s" % (prefix, distribution, err_data),
                        original_exception = e,
                        logger = logger)

    return update_result


def search_package_in_repo(client, repo, name=None, version=None, architecture=None):
    """
    Simple interface to query aply local repos for packages.
    It searches by control file fields (namely Name, Version, Architecture)
    Name and Architecture are searched by wildcard ([^]?* symbols).
    Version filed is searched  by operators >=, <=, =, >>, << according to apt rules.
    Operator must precede version (e.g. ">=1.0.1" or ">= 1.0.1"). If not, default is '='.
    Fields search expressions are ANDed together.
    It returns list of keys of found packages.
    """
    query_parts = []
    if name:
        query_parts.append("Name (% {})".format(name))
    if version:
        query_parts.append("$Version ({})".format(version))
    if architecture:
        query_parts.append("$Architecture (% {})".format(architecture))

    query = ", ".join(query_parts)
    search_result = client.repos.search_packages(repo, query)
    
    return [ s[0] for s in search_result ]

 
