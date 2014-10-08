# Source side

from __future__ import print_function

import gzip
import logging
import os
import tempfile
import urlparse

from fetch import fetch_contents
from filehash import *
from hashlist_op_impl import (hashlist_generate, sigfile_write,
                              hashlist_from_stringlist)
from lockfile import LockFileManager
from utility import cano_url

log = logging.getLogger()


##
## Source-side.
##


def source_side(opt, args):
    '''
    Implement the source-side of hsync.

    opt is the list of options from optparse, usually from the command line.

    Constructs the signature URL from the information in opt.

    args is ignored.

    Calls out to source_generate() to build the new HSYNC.SIG* file.
    '''
    # If there's an existing hashfile, optionally use it to try to reduce the
    # amount of scanning.

    abs_hashfile = _generate_hashfile_url(opt)

    # Lock the source-side hash file.
    abs_lockfile = abs_hashfile + '.lock'

    # Generate the new hashfile.
    with LockFileManager(abs_lockfile):
        return source_generate(abs_hashfile, opt)


def source_generate(abs_hashfile, opt):
    '''
    Generate a hash of the local filesystem, optionally using existing
    signatures to speed up the process.
    '''

    existing_hl = None

    if not opt.always_checksum and os.path.exists(abs_hashfile):
        if not opt.quiet:
            print("Reading existing hashfile")

        # Fetch the signature file.
        hashfile_contents = fetch_contents('file://' + abs_hashfile, opt,
                                            short_name=opt.hash_file)
        # Turn into a hashlist.
        existing_hl = _read_hashlist(abs_hashfile, opt)

    hashlist = hashlist_generate(opt.source_dir, opt,
                                    existing_hashlist=existing_hl)

    if hashlist is not None:

        write_success = sigfile_write(hashlist, abs_hashfile, opt,
                                        use_tmp=True)
        if not write_success:
            log.error("Failed to write signature file '%s'",
                os.path.join(opt.source_dir, opt.hash_file))
            return False

        return True

    else:
        log.error("Send-side generate failed")
        return False


def _generate_hashfile_url(opt):

    abs_hashfile = None

    if opt.signature_url:
        hashurl = cano_url(opt.signature_url)
        log.debug("Explicit signature URL '%s'", hashurl)
        up = urlparse.urlparse(hashurl)
        if up.scheme != 'file':
            raise URLMustBeOfTypeFileError(
                "Signature URL '%s' must be a local file", hashurl)
        abs_hashfile = up.path
        log.debug("Explicit signature file '%s'", abs_hashfile)

    else:
        hashfile = 'HSYNC.SIG'
        if opt.hash_file:
            hashfile = opt.hash_file
        if opt.compress_signature:
            hashfile += '.gz'

        abs_hashfile = os.path.join(opt.source_dir, hashfile)
        log.debug("Synthesised hash file location: '%s'", abs_hashfile)

    return abs_hashfile


def _read_hashlist(abs_hashfile, opt):
    # Fetch the signature file.
    hashfile_contents = fetch_contents('file://' + abs_hashfile, opt,
                                                short_name=opt.hash_file)

    if opt.compress_signature:
        gziptmp = tempfile.NamedTemporaryFile()
        with gziptmp:
            gziptmp.file.write(hashfile_contents)
            gziptmp.file.close()
            strfile = []
            for l in gzip.open(gziptmp.name):
                strfile.append(l.rstrip())

    else:
        strfile = hashfile_contents.splitlines()

    existing_hl = hashlist_from_stringlist(strfile, opt, root=opt.source_dir)
