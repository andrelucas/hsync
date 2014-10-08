# Utilities that don't fit elsewhere.

import fnmatch
import logging
import os
import urlparse

log = logging.getLogger()


def cano_url(url, slash=False):
    '''
    Given a URL or bare file path, return a URL in a well-known form. File
    paths become file URLS, and (if requested) the URL is slash-terminated.
    '''

    log.debug("cano_url: %s", url)
    up = urlparse.urlparse(url)
    log.debug("urlparse: %s", up.geturl())
    if up.scheme == '':
        url = 'file://' + url
        log.debug("Add scheme, URL=%s", url)
    if slash and not url.endswith("/"):
        url += "/"
    return url


##
## hashlist_op_impl uses these.
##


def is_dir_excluded(fpath, direx, direx_glob, excluded_dirs=None):
    '''
    Take a list of dirs, return a list minus directories we exclude for one
    reason or another.
    '''
    exclude = False
    if excluded_dirs is None:
        excluded_dirs = set()

    if fpath in direx:
        log.debug("%s: Exclude dir", fpath)
        dpath = fpath.rstrip(os.sep) + os.sep  # Make sure it ends in '/'.
        excluded_dirs.add(dpath)
        log.debug("Added exclusion dir: '%s'", dpath)
        exclude = True

    # Process directory globs.
    if not exclude:
        for glob in direx_glob:
            if fnmatch.fnmatch(fpath, glob):
                log.debug("%s: Exclude dir from glob '%s'", fpath, glob)
                dpath = fpath.rstrip(os.sep) + os.sep
                excluded_dirs.add(dpath)
                log.debug("Added exclusion dir: '%s'", dpath)
                exclude = True

    if not exclude:  # No point checking twice.
        for exc in excluded_dirs:
            if fpath.startswith(exc):
                log.debug("Excluded '%s': Under '%s'", fpath, exc)
                exclude = True

    return exclude


def is_path_pre_excluded(fpath, excluded_dirs, is_dir=False):
    '''
    For any object type, see if it's excluded by any existing exclusion
    dir. This is a lot cheaper than handling globs etc.
    '''
    if is_dir:
        fpath += os.sep

    for d in excluded_dirs:
        if fpath.startswith(d):
            log.debug("Excluding '%s' under excluded dir '%s'",
                      fpath, d)
            return True

    return False
