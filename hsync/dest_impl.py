# Dest side.

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

from __future__ import print_function

import gzip
import logging
import os
import os.path
import tempfile
import urllib2
import urlparse

from fetch import fetch_contents, fetch_needed, delete_not_needed
from filehash import *
from hashlist_op_impl import (sigfile_write, hashlist_from_stringlist,
                              hashlist_check)
from local_pwmgr import InstrumentedHTTPPassManager
from lockfile import LockFileManager
from utility import cano_url

log = logging.getLogger()


class BadAuthSpecificationError(Exception):

    pass


class BadProxySpecificationError(Exception):

    pass


##
# Dest-side.
##


def dest_side(opt, args):
    '''
    Implement the dest (client) side of hsync.

    opt is the list of command-line options, usually generated by optparse in
    hsync.main().

    args is interpreted as a list of filter options, to allow sync of specific
    pieces of the source.

    '''

    if opt.source_url is None:
        log.error("-u/--source-url must be defined for -D/--dest-dir mode")
        return False

    if args:
        log.debug("Interpreting command line arguments %s as --include items",
                  args)
        if opt.include is None:
            opt.include = []
        opt.include.extend(args)

    if opt.include and not opt.no_delete:
        log.warn("In -I/--include mode, option --no-delete is always on")
        opt.no_delete = True

    # Assemble the chain of urllib2 openers that we need to do potentially
    # more than one type of auth.

    auth_handler = _configure_http_auth(opt)

    proxy_handlers = None
    if opt.proxy_url:
        log.debug("Configuring proxy")
        proxy_handlers = _configure_http_proxy(opt)

    handlers = []
    if proxy_handlers is not None:
        handlers.extend(list(proxy_handlers))
    if auth_handler is not None:
        handlers.append(auth_handler)

    if handlers:
        log.debug("Building opener: Handlers %s", handlers)
        opener = urllib2.build_opener(*handlers)

        log.debug("Installing urllib2 opener: %s", opener)
        urllib2.install_opener(opener)

    (hashurl, shortname, compressed_sig) = _configure_hashurl(opt)

    # Fetch the signature file.
    if not opt.quiet:
        print("Fetching remote hashfile")

    hashfile_contents = fetch_contents(hashurl, opt,
                                       short_name=shortname,
                                       include_in_total=False)

    if hashfile_contents is None:
        # We're not coming back from this.
        log.error("Failed to retrieve signature file from '%s", hashurl)
        return False

    if compressed_sig:
        gziptmp = tempfile.NamedTemporaryFile()
        with gziptmp:
            gziptmp.file.write(hashfile_contents)
            gziptmp.file.close()
            src_strfile = []
            for l in gzip.open(gziptmp.name):
                src_strfile.append(l.rstrip())
    else:
        src_strfile = hashfile_contents.splitlines()

    # Release hashfile contents from memory.
    hashfile_contents = None

    if not src_strfile[-1].startswith("FINAL:"):
        raise TruncatedHashfileError("'FINAL:'' line of hashfile %s appears "
                                     "to be missing!" % hashurl)
    src_hashlist = hashlist_from_stringlist(src_strfile, opt,
                                            root=opt.dest_dir)

    opt.source_url = cano_url(opt.source_url, slash=True)
    log.debug("Source url '%s", opt.source_url)

    abs_hashfile = os.path.join(opt.dest_dir, opt.hash_file)
    abs_lockfile = abs_hashfile + '.lock'
    log.debug("abs_hashfile '%s' abs_lockfile '%s'",
              abs_hashfile, abs_lockfile)

    if not os.path.isdir(opt.dest_dir):
        os.makedirs(opt.dest_dir)

    with LockFileManager(abs_lockfile):

        return _dest_impl(abs_hashfile, src_hashlist, shortname, opt)


def _dest_impl(abs_hashfile, src_hashlist, shortname, opt):

    existing_hl = None

    # Make a note of whether or not an old hashfile exists.
    old_hashfile_exists = os.path.exists(abs_hashfile)

    if not opt.always_checksum and old_hashfile_exists:
        if not opt.quiet:
            print("Reading existing hashfile")

        # Fetch the signature file.
        hashfile_contents = fetch_contents('file://' + abs_hashfile, opt,
                                           short_name=shortname,
                                           remote_flag=False,
                                           include_in_total=False)
        dst_strfile = hashfile_contents.splitlines()
        existing_hl = hashlist_from_stringlist(dst_strfile, opt,
                                               root=opt.dest_dir)

    # Calculate the differences to the local filesystem.
    #
    # Since we've just done a scan, write the results to the disk - then,
    # if something goes wrong, at least we've saved the scan results.
    (needed, not_needed, dst_hashlist) = \
        hashlist_check(opt.dest_dir,
                       src_hashlist, opt,
                       existing_hashlist=existing_hl,
                       opportunistic_write=True,
                       opwrite_path=abs_hashfile,
                       source_side=False)

    if opt.verify_only:
        return _verify_impl(needed, not_needed, opt)
    else:
        return _fetch_remote_impl(needed, not_needed,
                                  dst_hashlist, abs_hashfile, opt)


def _verify_impl(needed, not_needed, opt):
    # Give a report if we're verbose.
    needed_is_real = False

    if needed:
        shown_header = False

        for fh in needed:
            if not fh.is_dir:
                needed_is_real = True

                if not opt.quiet:
                    if not shown_header:
                        print("Files needing transfer:")
                        shown_header = True

                    print("+ %s" % fh.fpath, end='')
                    if not fh.dest_missing and \
                            not fh.contents_differ and fh.metadata_differs:
                        print(" (metadata change only)")
                    else:
                        print('')

    if not opt.no_delete and not_needed:
        shown_header = False

        for fh in not_needed:
            if not shown_header:
                print("Files needing deletion:")
                shown_header = True

            needed_is_real = True
            if not opt.quiet:
                print("- %s" % fh.fpath)

    if needed_is_real:
        return False
    else:
        # True ('verified') means 'nothing to do'.
        return True


def _fetch_remote_impl(needed, not_needed, dst_hashlist, abs_hashfile, opt):

    # fetch_needed() does almost all the work.
    (fetch_added, fetch_err_count) = fetch_needed(needed, opt.source_url, opt)

    # Don't delete things if we had transfer problems. It's safer.
    delete_status = True
    if not opt.no_delete and fetch_err_count == 0:
        delete_status = delete_not_needed(not_needed, opt.dest_dir, opt)

    if (fetch_err_count > 0 or not delete_status):
        log.error("Sync failed")
        return False

    if len(fetch_added) > 0:
        log.debug("Adding %d new entries to destination hashlist",
                  len(fetch_added))
        dst_hashlist.extend(fetch_added)

    if not opt.no_write_hashfile and dst_hashlist is not None:
        if not sigfile_write(dst_hashlist, abs_hashfile, opt,
                             use_tmp=True, verb='Writing',
                             no_compress=True):
            log.error("Failed to write signature file '%s'",
                      os.path.join(opt.source_dir, opt.hash_file))
            return False

    if not opt.quiet:
        if fetch_added:
            print("Files added:")
            for fh in fetch_added:
                print("+ %s" % fh.fpath)

        if not_needed:
            if opt.no_delete:
                print("\nCandidates for removal (--no-delete is active):")
            else:
                print("\nObjects removed:")
            for fh in not_needed:
                print("- %s" % fh.fpath)

    if opt.verbose:
        print("\nRaw %s:" % opt.stats.name())
        for k, v in opt.stats.iteritems():
            print("  %s = %s" % (k, v))
        print('')

    return True


def _configure_http_auth(opt):
    '''
    Configure HTTP authentication.

    All on urllib2 objects, no return.
    '''

    if opt.http_auth_type != 'digest' and opt.http_auth_type != 'basic':
        log.error("HTTP auth type must be one of 'digest' or 'basic'")
        raise BadAuthSpecificationError(
            "Bad authentication type '%s'" % (opt.http_auth_type))

    if opt.http_user:
        log.debug("Configuring HTTP authentication")
        if not opt.http_pass:
            log.error("HTTP password must be specified when the username "
                      "is supplied")
            raise BadAuthSpecificationError(
                "No password given for user '%s'" % opt.http_user)

        pwmgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        pwmgr.add_password(None, opt.source_url,
                           opt.http_user, opt.http_pass)

        if opt.http_auth_type == 'digest':
            log.debug("Configuring digest authentication")
            return urllib2.DigestAuthHandler(pwmgr)

        else:
            log.debug("Configuring basic authentication")
            return urllib2.HTTPBasicAuthHandler(pwmgr)


def _configure_http_proxy(opt):
    '''
    Configure an HTTP proxy. Return a list of handlers to be given to
    urllib2.build_opener().

    '''

    schemes = {}
    for scheme in ('ftp', 'http', 'https'):
        schemes[scheme] = opt.proxy_url

    host = urlparse.urlsplit(opt.source_url)[1]
    log.debug("Using '%s' as URI host for '%s'", host, opt.source_url)

    log.debug("Installing handlers: %s", schemes)
    proxy_handler = urllib2.ProxyHandler(schemes)

    if opt.proxy_user and opt.proxy_pass:
        log.debug("Configuring HTTP proxy authentication")
        if not opt.proxy_pass:
            log.error("HTTP proxy password ")
            raise BadProxySpecificationError(
                "No password given for proxy user '%s'" % opt.proxy_user)

        pwmgr = InstrumentedHTTPPassManager()
        pwmgr.add_password(None, host, opt.proxy_user, opt.proxy_pass)

        proxy_auth_handler = urllib2.ProxyBasicAuthHandler(pwmgr)
        return (proxy_handler, proxy_auth_handler)

    else:
        return (proxy_handler,)


def _configure_hashurl(opt):

    hashurl = None
    hashfile = opt.hash_file
    shortname = hashfile
    compressed_sig = False

    if opt.remote_sig_compressed:
        hashfile += '.gz'
        compressed_sig = True

    if opt.signature_url:
        hashurl = cano_url(opt.signature_url)
        log.debug("Explicit signature URL '%s'", hashurl)

        p_url = urlparse.urlparse(hashurl)
        u_path = p_url.path
        shortname = os.path.basename(u_path)

        if opt.signature_url.endswith('.gz'):
            log.debug("Assuming compression for signature URL '%s'",
                      opt.signature_url)
            compressed_sig = True

        if opt.remote_sig_compressed:
            log.debug("Force remote signature compression mode")
            compressed_sig = True

    else:
        if opt.remote_sig_compressed:
            compressed_sig = True
            shortname += '.gz'

        hashurl = cano_url(opt.source_url, slash=True) + hashfile
        log.debug("Synthesised signature URL '%s'", hashurl)

    log.debug("_configure_hashurl(): hashurl=%s shortname=%s "
              "compressed_sig=%s", hashurl, shortname, compressed_sig)

    return (hashurl, shortname, compressed_sig)
