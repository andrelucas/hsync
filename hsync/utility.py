# Utilities that don't fit elsewhere.

import fnmatch
import logging
import os
import re
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
## hashlist_op_impl exclusion processing.
##


def is_dir_excluded(fpath, direx, direx_glob, excluded_dirs=None):
    '''
    Given a dir, return True if the user excluded the directory, false
    otherwise.
    '''
    exclude = False
    if excluded_dirs is None:
        excluded_dirs = set()

    if fpath in direx:
        log.debug("'%s': Exclude dir", fpath)
        dpath = fpath.rstrip(os.sep) + os.sep  # Make sure it ends in '/'.
        excluded_dirs.add(dpath)
        log.debug("Added exclusion dir: '%s'", dpath)
        exclude = True

    # Process directory globs.
    if not exclude:
        for glob in direx_glob:
            if fnmatch.fnmatch(fpath, glob):
                log.debug("'%s': Exclude dir from glob '%s'", fpath, glob)
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
    For any object type, see if it's excluded by any existing exclusion dir.
    This is a lot cheaper than handling globs etc.
    '''
    if is_dir:
        fpath += os.sep

    for d in excluded_dirs:
        if fpath.startswith(d):
            log.debug("Excluding '%s' under excluded dir '%s'",
                      fpath, d)
            return True

    return False


##
## Inclusion processing.
##

def is_path_included(fpath, inclist, inclist_glob, included_dirs=None,
                     is_dir=False):
    '''
    Given a path and the user's inclusion lists, return True if the path is
    specifically included by the user, False otherwise.

    included_dirs is used as a cache for globs, so we don't have to fnmatch()
    them each time.
    '''
    include = False
    if included_dirs is None:
        included_dirs = set()

    # Use the is_dir to flag a directory, don't care about trailing slashes.
    fpath = fpath.rstrip(os.sep)

    if log.isEnabledFor(logging.DEBUG):
        log.debug("is_path_included: '%s' inclist %s inclist_glob %s "
                  "is_dir %s included_dirs %s",
                fpath, inclist, inclist_glob, is_dir, included_dirs)

    if fpath in inclist:
        log.debug("'%s': Include", fpath)
        include = True
        if is_dir:
            included_dirs.add(fpath + os.sep)

    if not include:
        # Check if it's underneath something that's already included.
        for d in included_dirs:
            if fpath.startswith(d):
                log.debug("Including '%s' under included dir '%s'",
                          fpath, d)
                include = True

    if not include:
        for glob in inclist_glob:
            if fnmatch.fnmatch(fpath, glob):
                log.debug("'%s': Include path from glob '%s'", fpath, glob)
                include = True
                if is_dir:
                    included_dirs.add(fpath + os.sep)
                    log.debug("Added inclusion dir '%s'", fpath)


    return include
