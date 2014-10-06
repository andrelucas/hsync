# Dest side.

from __future__ import print_function

from fnmatch import fnmatch
import gzip
import logging
import os
import tempfile
import urlparse

from fetch import fetch_contents, fetch_needed, delete_not_needed
from filehash import *
from hashlist_op_impl import (hashlist_generate, sigfile_write,
								 hashlist_from_stringlist, hashlist_check)
from lockfile import LockFileManager
from utility import cano_url

log = logging.getLogger()


##
## Dest-side.
##


def dest_side(opt, args):

    if opt.source_url is None:
        log.error("-u/--source-url must be defined for -D/--dest-dir mode")
        return False

    compressed_sig = False

    if opt.http_auth_type != 'digest' and opt.http_auth_type != 'basic':
        log.error("HTTP auth type must be one of 'digest' or 'basic'")
        return False

    if opt.http_user:
        log.debug("Configuring HTTP authentication")
        if not opt.http_pass:
            log.error("HTTP proxy password must be specified")

        pwmgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        pwmgr.add_password(None, opt.source_url,
                            opt.http_user, opt.http_pass)
        auth_opener = None
        if opt.http_auth_type == 'digest':
            log.debug("Configuring digest authentication")
            auth_opener = urllib2.build_opener(urllib2.DigestAuthHandler(pwmgr))

        else:
            log.debug("Configuring basic authentication")
            auth_opener = urllib2.build_opener(urllib2.HTTPBasicAuthHandler(pwmgr))

        urllib2.install_opener(auth_opener)

    if opt.proxy_url:
        log.debug("Configuring proxy")
        raise Exception("Explicit proxy not yet implemented, use "
                            "environment variables")

    hashurl = None
    hashfile = opt.hash_file
    shortname = hashfile

    if opt.remote_sig_compressed:
        hashfile += '.gz'
        compressed_sig = True

    if opt.signature_url:
        hashurl = cano_url(opt.signature_url)
        log.debug("Explicit signature URL '%s'", hashurl)

        if opt.signature_url.endswith('.gz'):  # XXX might fail with funny URLs.
            log.debug("Assuming compression for signature URL '%s'", opt.signature_url)
            compressed_sig = True
            shortname += '.gz'

        if opt.remote_sig_compressed:
            log.debug("Force remote signature compression mode")
            compressed_sig = True

    else:
        if opt.remote_sig_compressed:
            compressed_sig = True
            shortname += '.gz'

        hashurl = cano_url(opt.source_url, slash=True) + hashfile
        log.debug("Synthesised signature URL '%s'", hashurl)

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

    if not src_strfile[-1].startswith("FINAL:"):
        raise TruncatedHashfileError("'FINAL:'' line of hashfile %s appears to be missing!" % hashurl)

    src_hashlist = hashlist_from_stringlist(src_strfile, opt, root=opt.dest_dir)

    opt.source_url = cano_url(opt.source_url, slash=True)
    log.debug("Source url '%s", opt.source_url)

    abs_hashfile = os.path.join(opt.dest_dir, opt.hash_file)
    abs_lockfile = abs_hashfile + '.lock'
    log.debug("abs_hashfile '%s' abs_lockfile '%s'", abs_hashfile, abs_lockfile)
    existing_hl = None

    if not os.path.isdir(opt.dest_dir):
        os.makedirs(opt.dest_dir)

    with LockFileManager(abs_lockfile):

        # Make a note of whether or not an old hashfile exists.
        old_hashfile_exists = os.path.exists(abs_hashfile)

        if not opt.always_checksum and old_hashfile_exists:
            if not opt.quiet:
                print("Reading existing hashfile")

            # Fetch the signature file.
            hashfile_contents = fetch_contents('file://' + abs_hashfile, opt,
                                                        short_name=opt.hash_file,
                                                        remote_flag=False,
                                                        include_in_total=False)
            dst_strfile = hashfile_contents.splitlines()
            existing_hl = hashlist_from_stringlist(dst_strfile, opt, root=opt.dest_dir)

        # Calculate the differences to the local filesystem.
        #
        # Since we've just done a scan, write the results to the disk - then, if
        # Something goes wrong, at least we've saved the scan results.
        (needed, not_needed, dst_hashlist) = hashlist_check(opt.dest_dir,
                                                src_hashlist, opt,
                                                existing_hashlist=existing_hl,
                                                opportunistic_write=True,
                                                opwrite_path=abs_hashfile,
                                                source_side=False)

        if opt.verify_only:
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
                            if not fh.contents_differ and fh.metadata_differs:
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

        else:
            fetch_added = fetch_needed(needed, opt.source_url, opt)
            if fetch_added is not None:
                delete_status = delete_not_needed(not_needed, opt.dest_dir, opt)

            if (fetch_added is None or not delete_status):
                log.error("Sync failed")
                return False

            if fetch_added is not None:
                log.debug("Adding new entries to destination hashlist")
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
                    print("\nFiles removed:")
                    for fh in not_needed:
                        print("- %s" % fh.fpath)

            if opt.verbose:
                print("\nRaw %s:" % opt.stats.name())
                for k, v in opt.stats.iteritems():
                    print("  %s = %s" % (k, v))
                print('')

            return True
