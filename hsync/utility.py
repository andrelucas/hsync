# Utilities that don't fit elsewhere.

# Copyright (c) 2015, Andre Lucas
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the <organization> nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import fnmatch
import logging
import os
import urlparse

from hashlist import HashList
from hashlist_sqlite import SqliteHashList

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


def dumpframe(header="", depth=4):
    '''
    Dump the call frame for the caller, minus the call to this function
    which is unlikely to be helpful information.

    Only does anything at loglevel DEBUG, so it is safe to call unguarded
    when not debugging.
    '''

    if not log.isEnabledFor(logging.DEBUG):
        return

    import inspect
    prev = inspect.stack(1)[1]
    cname = "%s:%s:%s" % (prev[0], prev[1], prev[2])

    import traceback
    log.debug("%s: BEGIN dumpframe() for %s", header, cname)

    # Get the call stack minus this call to dumpframe().
    stack = traceback.format_stack()[:-1]
    if depth < len(stack):
        stack = stack[(-depth):]

    for n, line in enumerate(stack):
        log.debug("frame[%d]: %s", depth-n, line.rstrip())
    log.debug("%s: END   dumpframe() for %s", header, cname)


#
# Return the correct HashList type based on the options given by the user.
#

def get_hashlist(opts):
    '''
    If the user asks to reduce memory use, return a disk-backed HashList
    object, which will obviously run much more slowly than the default
    memory-backed HashList object.
    '''

    if opts.use_less_memory:
        log.debug("get_hashlist(): Returning Sqlite-backed hashlist object")
        return SqliteHashList()
    else:
        log.debug("get_hashlist(): Returning memory-backed hashlist object")
        return HashList()

#
# hashlist_op_impl exclusion processing.
#

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


##
## Hashfile detection.
##

def is_hashfile(filename, custom_hashfile=None,
                allow_locks=True, allow_compressed=True):

    '''
    Given a path, return True if it looks like a hashfile, False
    otherwise.

    Optionally, also return True if the path is a lockfile.
    '''

    log.debug("is_hashfile(%s, custom_hashfile=%s, allow_locks=%s, "
              "allow_compressed=%s)",
              filename, custom_hashfile, allow_locks, allow_compressed)

    # Empty string is a coding error.
    if custom_hashfile == '':
        raise Exception("Empty string is not a valid hashfile name")

    # Always check for the default hashfile HSYNC.SIG{.gz}.
    if filename == 'HSYNC.SIG':
        return True

    if allow_locks:
        if filename == 'HSYNC.SIG.lock':
            return True

    if allow_compressed and filename == 'HSYNC.SIG.gz':
        return True

    if allow_compressed and allow_locks and filename == 'HSYNC.SIG.gz.lock':
        return True


    if custom_hashfile is not None and custom_hashfile != 'HSYNC.SIG':
        if filename == custom_hashfile:
            return True
        if allow_locks and filename == '%s.lock' % custom_hashfile:
            return True
        if allow_compressed and filename == '%s.gz' % custom_hashfile:
            return True
        if (allow_compressed and allow_locks and
            filename == '%s.gz.lock' % custom_hashfile):
            return True

    return False
