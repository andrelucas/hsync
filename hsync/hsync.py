#!/usr/bin/env python

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

# Simple sync-in-the-clear tool. Use SHA* and http to sync two
# directories using only HTTP GET.

from __future__ import print_function

import hashlib
import logging
import optparse
import os.path
from stat import *
import sys
import urlparse

from dest_impl import dest_side
from exceptions import *
from filehash import *
from idmapper import *
from source_impl import source_side
from stats import StatsCollector


log = logging.getLogger()


def getopts(cmdargs):

    p = optparse.OptionParser()

    send = optparse.OptionGroup(p, "Send-side options")
    send.add_option("-S", "--source-dir",
                    help="Specify the source directory")
    send.add_option("-z", "--compress-signature", action="store_true",
                    help="Compress the signature file using zlib")
    p.add_option_group(send)

    recv = optparse.OptionGroup(p, "Receive-side options")
    recv.add_option("-D", "--dest-dir",
                    help="Specify the destination directory")
    recv.add_option("-u", "--source-url",
                    help="Specify the data source URL")
    recv.add_option("-I", "--include", action="append",
                    help="Specify a list of files to really transfer. This "
                    "is applied after all other options and can be used to "
                    "narrow the scope of a fetch to specific files or "
                    "directories. Can also be specified as regular arguments "
                    "after all other options")
    recv.add_option("--no-delete", action="store_true",
                    help="Never remove files from the destination, even if "
                    "they're not present on the source")
    recv.add_option("-Z", "--remote-sig-compressed", action="store_true",
                    help="Fetch remote HSYNC.SIG.gz instead of HSYNC.SIG")
    recv.add_option("--set-user",
                    help="Specify the owner for local files")
    recv.add_option("--set-group",
                    help="Specify the group for local files")
    recv.add_option("--no-write-hashfile", action="store_true",
                    help="Don't write a signature file after sync")
    recv.add_option("--ignore-mode", action="store_true",
                    help="Ignore differences in file modes")
    recv.add_option("--http-user",
                    help="Specify the HTTP auth user")
    recv.add_option("--http-pass",
                    help="Specify the HTTP auth password")
    recv.add_option("--http-auth-type", default='basic',
                    help="Specify HTTP auth type (basic|digest) "
                    "[default: %default]")
    recv.add_option("--proxy-url",
                    help="Specify the proxy URL to use")
    recv.add_option("--proxy-user",
                    help="Specify the proxy authentication username")
    recv.add_option("--proxy-pass",
                    help="Specify the proxy authentication password")
    p.add_option_group(recv)

    recv.add_option("-U", "--signature-url",
                    help="Specify the signature file's URL [default: "
                    "<source_url>/HSYNC.SIG]")

    meta = optparse.OptionGroup(p, "Other options")
    meta.add_option("--version", action="store_true",
                    help="Show the program version")
    meta.add_option("-V", "--verify-only", action="store_true",
                    help="Verify only, do not transfer or delete files")
    meta.add_option("--fail-on-errors", action="store_true",
                    help="Fail on any error. Default is to try to carry on")
    meta.add_option("-c", "--always-checksum", action="store_true",
                    help="Always read and re-checksum files, never trust "
                    "file modification times or other metadata")
    meta.add_option("--hash-file", default="HSYNC.SIG",
                    help="Specify the hash filename [default: %default]")
    meta.add_option("--no-ignore-dirs", action="store_true",
                    help="Don't trim common dirs such as .git, .svn and CVS")
    meta.add_option("--no-ignore-files", action="store_true",
                    help="Don't trim common ignore-able files such as *~ and "
                    "*.swp")
    meta.add_option("--no-trim-path", action="store_false",
                    default=True, dest='trim_path',
                    help="Don't trim the top-level path from filenames. It's "
                    "safer to leave this well alone.")
    meta.add_option("-X", "--exclude-dir", action="append",
                    help="Specify a directory path (relative to the root) to "
                    "ignore. On the server side, this simply doesn't "
                    "checksum the file, which has the effect of rendering it "
                    "invisible (and deletable!) on the client side. On the "
                    "client side, it prevents processing of the path.")
    meta.add_option("--fetch-blocksize", default=32 * 1000,
                    help="Specify the number of bytes to retrieve at a time "
                    "[default: %default]")
    # This is used to pass stats around the app.
    meta.add_option("--stats", help=optparse.SUPPRESS_HELP)
    # Debugging tools.
    meta.add_option("--scan-debug", action="store_true",
                    help=optparse.SUPPRESS_HELP)
    meta.add_option("--check-debug", action="store_true",
                    help=optparse.SUPPRESS_HELP)
    meta.add_option("--fetch-debug", action="store_true",
                    help=optparse.SUPPRESS_HELP)

    p.add_option_group(meta)

    output = optparse.OptionGroup(p, "Output options")

    output.add_option("-v", "--verbose", action="store_true",
                      help="Enable verbose output")
    output.add_option("-d", "--debug", action="store_true",
                      help="Enable debugging output")
    output.add_option("-q", "--quiet", action="store_true",
                      help="Reduce output further")
    recv.add_option("-P", "--progress", action="store_true",
                    help="Show download progress")

    p.add_option_group(output)

    (opt, args) = p.parse_args(args=cmdargs)

    return (opt, args)


def init_stats():
    '''Initialise a StatsCollector for the application to use.'''
    stattr = [
        # rsync-style 'savings' measurement.
        'bytes_total',
        'bytes_transferred',
        'metadata_bytes_transferred',

        # fetch_contents()
        'content_fetches',
        'metadata_fetches',

        # Fetch stats.
        'file_contents_differed',
        'file_metadata_differed',
        'directory_metadata_differed',
        'link_contents_differed',
        'link_metadata_differed',

    ]
    return StatsCollector.init('AppStats', stattr)


def main(cmdargs):

    (opt, args) = getopts(cmdargs)

    if opt.version:
        from _version import __version__
        print("Hsync version %s" % __version__)
        return True

    level = logging.WARNING
    if opt.verbose:
        level = logging.INFO
    if opt.debug:
        level = logging.DEBUG
        opt.verbose = True

    logging.basicConfig(level=level)
    log = logging.getLogger()

    if opt.quiet and (opt.verbose or opt.debug):
        log.error("It doesn't make sense to mix quiet and verbose options")
        return False

    # As soon as logging is configured, say what we're doing.
    if log.isEnabledFor(logging.DEBUG):
        log.debug("main: args %s", cmdargs)

    opt.stats = init_stats()

    # Unbuffering stdout fails if stdout is, for example, a StringIO.
    try:
        log.debug("Setting stdout to unbuffered")
        sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
    except AttributeError as e:
        log.debug("Failed to unbuffer stdout, may be in test mode (%s)", e)

    if opt.source_dir and opt.dest_dir:
        log.error("Send-side and receive-side options can't be mixed")
        return False

    if log.isEnabledFor(logging.DEBUG):
        log.debug("hashlib.algorithms: %s", hashlib.algorithms)

    if 'sha256' not in hashlib.algorithms:
        log.error("No SHA256 implementation in hashlib!")
        return False

    # Send-side.
    if opt.source_dir:
        return source_side(opt, args)

    # Receive-side.
    elif opt.dest_dir:

        # Quickly check if the user and group settings are ok.
        m = UidGidMapper()
        if opt.set_user:
            m.set_default_name(opt.set_user)
        if opt.set_group:
            m.set_default_group(opt.set_group)

        # Try to guess the -u setting if only -U is given.
        if opt.signature_url and not opt.source_url:
            up = urlparse.urlparse(opt.signature_url)
            opt.source_url = urlparse.urlunparse([up.scheme, up.netloc,
                                                  os.path.dirname(up.path),
                                                  '', '', ''])
            log.debug("Synthesised source URL '%s' from signature URL '%s'",
                      opt.source_url, opt.signature_url)

        return dest_side(opt, args)

    else:
        print("You gave me nothing to do! Try '%s --help'." %
              os.path.basename(sys.argv[0]))
        return True


def csmain():
    if not main(sys.argv[1:]):
        sys.exit(1)


if __name__ == '__main__':
    csmain()
