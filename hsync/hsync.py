#!/usr/bin/env python

# Simple sync-in-the-clear tool. Use SHA* and http to sync two
# directories using only HTTP GET.

from __future__ import print_function

from BaseHTTPServer import BaseHTTPRequestHandler
import fnmatch
import grp
import gzip
import hashlib
import logging
import optparse
import os.path
import pwd
from random import SystemRandom
import re
from stat import *
import sys
import tempfile
import urllib2
import urlparse

from dest_impl import dest_side
from exceptions import *
from filehash import *
from hashlist_op_impl import hashlist_generate
from idmapper import *
from lockfile import LockFileManager
from numformat import IECUnitConverter as IEC
from source_impl import source_side
from stats import StatsCollector


log = logging.getLogger()

class URLMustBeOfTypeFileError(Exception): pass
class ContentsFetchFailedError(Exception): pass
class TruncatedHashfileError(Exception): pass



def fetch_needed(needed, source, opts):
    '''
    Download/copy the necessary files from opts.source_url or opts.source_dir
    to opts.dest_dir.

    This is a bit fiddly, as it tries hard to get the modes right.

    Returns a list of FileHash objects we /added/ as a result of this run, or
    None on failure.
    '''

    r = SystemRandom()
    mapper = UidGidMapper()
    fetch_added = []
    errorCount = 0

    if not source.endswith('/'):
        source += "/"

    contents_differ_count = 0
    differing_file_index = 0

    for fh in needed:
        if fh.dest_missing or fh.contents_differ:
            contents_differ_count += 1

    # This is used to get current information into the destination
    # hashlist. That way, current information is written to the client
    # HSYNC.SIG, saving on re-scans.

    changed_contents = False
    changed_uidgid = False
    changed_mode = False
    changed_mtime = False

    def update_dest_filehash(src_fh):
        if src_fh.associated_dest_object is None:
            log.debug("Saved new file '%s' for inclusion in sigfile",
                        fh.fpath)
            fetch_added.append(fh)

        else:
            dst_fh = src_fh.associated_dest_object
            log.debug("Updating dest FileHash object for '%s", fh.fpath)

            if changed_contents:
                dst_fh.size = src_fh.size
                dst_fh.hashstr = src_fh.hashstr

            if changed_uidgid:
                dst_fh.uid = src_fh.uid
                dst_fh.gid = src_fh.gid

            if changed_mode:
                dst_fh.mode = src_fh.mode

            if changed_mtime:
                dst_fh.mtime = src_fh.mtime


    for n, fh in enumerate(needed, start=1):
        if log.isEnabledFor(logging.DEBUG):
            if fh.is_dir:
                log.debug("fetch_needed: dir %s", fh.fpath)
            else:
                log.debug("fetch_needed: %s", fh.fpath)

        source_url = urlparse.urljoin(source, fh.fpath)

        if fh.is_file:

            # if not opts.quiet:
            #     print("Get file: %s" % fh.fpath)

            tgt_file = os.path.join(opts.dest_dir, fh.fpath)
            tgt_file_rnd = tgt_file + ".%08x" % r.randint(0, 0xffffffff)

            if fh.dest_missing or fh.contents_differ:

                differing_file_index += 1

                opts.stats.file_contents_differed += 1

                log.debug("Fetching: '%s' dest_missing %s contents_differ %s",
                    fh.fpath, fh.dest_missing, fh.contents_differ)

                if not opts.quiet and sys.stdout.isatty():
                    print("F: %s\r" % fh.fpath, end='')

                # Fetch_contents will display progress information itself.
                contents = fetch_contents(source_url, opts, for_filehash=fh,
                    file_count_number=differing_file_index,
                    file_count_total=contents_differ_count)

                if contents is None:
                    if opts.fail_on_errors:
                        raise ContentsFetchFailedException(
                            "Failed to fetch '%s'" % source_url)
                    else:
                        log.debug("Failed to fetch '%s', continuing", fh.fpath)

                else:

                    changed_contents = True     # If we fetched it, we changed it.

                    chk = hashlib.sha256()
                    log.debug("Hashing contents")

                    if opts.progress:
                        print(' checking...', end='')

                    chk.update(contents)
                    log.debug("Contents hash done (%s)", chk.hexdigest())

                    if opts.progress:
                        print('done')

                    if chk.hexdigest() != fh.hashstr:
                        log.warn("File '%s' failed checksum verification!", fh.fpath)
                        errorCount += 1
                        continue

                    log.debug("Will write to '%s'", tgt_file_rnd)
                    if os.path.exists(tgt_file):
                        if os.path.islink(tgt_file):
                            raise ParanoiaError(
                                "Not overwriting existing symlink '%s' with file", tgt_file)
                        if os.path.isdir(tgt_file):
                            raise DirWhereFileExpectedError(
                                "Directory found where file expected at '%s'", tgt_file)

                    # Dealing with file descriptors, use os.f*() variants.
                    tgt = os.open(tgt_file_rnd, os.O_CREAT | os.O_EXCL | os.O_WRONLY, fh.mode)
                    if tgt == -1:
                        raise OSOperationFailedError("Failed to open '%s'", tgt_file_rnd)

                    expect_uid = fh.uid
                    expect_gid = fh.gid

                    filestat = os.stat(tgt_file_rnd)
                    if filestat.st_uid != expect_uid or filestat.st_gid != expect_gid:
                        changed_uidgid = True
                        log.debug("Changing file %s ownership to %s/%s",
                                    tgt_file_rnd, fh.user, fh.group)
                        if os.fchown(tgt, expect_uid, expect_gid) == -1:
                            log.warn("Failed to fchown '%s' to user %s group %s",
                                    tgt_file_rnd, fh.user, fh.group)

                    changed_mode = False # We didn't /change/ it, we created it.

                    os.write(tgt, contents)
                    os.close(tgt)
                    log.debug("Moving into place: '%s' -> '%s'", tgt_file_rnd, tgt_file)
                    if os.rename(tgt_file_rnd, tgt_file) == -1:
                        raise OSOperationFailedError("Failed to rename '%s' to '%s'",
                            tgt_file_rnd, tgt_file)

                    changed_mtime = True
                    os.utime(tgt_file, (fh.mtime, fh.mtime))

                    if changed_uidgid or changed_mtime or changed_mode:
                        opts.stats.file_metadata_differed += 1


            elif fh.metadata_differs:

                log.debug("'%s': metadata differs", fh.fpath)

                expect_uid = fh.uid
                expect_gid = fh.gid

                filestat = os.stat(tgt_file)

                if not opts.quiet:
                    print("F: %s" % (fh.fpath), end='')

                if filestat.st_uid != expect_uid or filestat.st_gid != expect_gid:
                    changed_uidgid = True
                    if not opts.quiet:
                        print(" (user/group: %s/%s -> %s/%s)" % (
                                                    filestat.st_uid, filestat.st_gid,
                                                    expect_uid, expect_gid), end='')
                    log.debug("Changing file %s ownership to %s/%s",
                                tgt_file, fh.user, fh.group)
                    if os.chown(tgt_file, expect_uid, expect_gid) == -1:
                        log.warn("Failed to fchown '%s' to user %s group %s",
                                tgt_file, fh.user, fh.group)

                if filestat.st_mode != fh.mode:
                    changed_mode = True
                    if not opts.quiet:
                        print(" (mode %06o -> %06o)" % (filestat.st_mode, fh.mode), end='')

                    log.debug("'%s': Setting mode: %06o", fh.fpath, fh.mode)
                    if os.chmod(tgt_file, fh.mode) == -1:
                        log.warn("Failed to fchmod '%s' to %06o", fh.fpath, fh.mode)

                if filestat.st_mtime != fh.mtime:
                    changed_mtime = True
                    if not opts.quiet:
                        print(" (mtime %d -> %d)" % (filestat.st_mtime, fh.mtime), end='')
                    os.utime(tgt_file, (fh.mtime, fh.mtime))

                opts.stats.file_metadata_differed += 1

                if not opts.quiet:
                    print('')



            elif fh.mtime_differs:
                log.debug("'%s': mtime differs", fh.fpath)
                changed_mtime = True

                if not opts.quiet:
                    filestat = os.stat(tgt_file)
                    print("F: %s (mtime %d -> %d)" % (fh.fpath,
                                        filestat.st_mtime, fh.mtime))

                os.utime(tgt_file, (fh.mtime, fh.mtime))
                opts.stats.file_metadata_differed += 1


        elif fh.is_link:
            linkpath = os.path.join(opts.dest_dir, fh.fpath)

            if not os.path.exists(linkpath):
                log.debug("Creating symlink '%s'->'%s'",
                            linkpath, fh.link_target)
                if not opts.quiet:
                    print("L: (create) %s -> %s" %
                            (linkpath, fh.link_target))
                os.symlink(fh.link_target, linkpath)
                opts.stats.link_contents_differed += 1

            else:
                log.debug("Path '%s' exists in the filesystem", linkpath)
                if not os.path.islink(linkpath):
                    raise NonLinkFoundAtLinkLocationError(
                        "Non-symlink found where we want a symlink ('%s')",
                        linkpath)

                else:
                    # Symlink found. Check it.
                    curtgt = os.readlink(linkpath)
                    # Create or move the symlink.
                    if curtgt != fh.link_target:
                        changed_contents = True
                        log.debug("Moving symlink '%s'->'%s'",
                                     linkpath, dh.link_target)
                        if not opts.quiet:
                            print("L: (move) %s -> %s" %
                                    (linkpath, fh.link_target))
                        os.symlink(fh.link_target, linkpath)
                        opts.stats.link_contents_differed += 1

            expect_uid = fh.uid
            expect_gid = fh.gid

            lstat = os.lstat(linkpath)
            if lstat.st_uid != expect_uid or lstat.st_gid != expect_gid:
                changed_uidgid = True
                log.debug("Changing link '%s' ownership to %s/%s",
                    linkpath, expect_uid, expect_gid)
                os.lchown(linkpath, expect_uid, expect_gid)

            if lstat.st_mode != fh.mode:
                changed_mode = True
                log.debug("Changing link '%s' mode to %06o",
                            linkpath, fh.mode)
                os.lchmod(linkpath, fh.mode)

            if changed_mode or changed_uidgid:
                opts.stats.link_metadata_differed += 1


        elif fh.is_dir:
            tgt_dir = os.path.join(opts.dest_dir, fh.fpath)
            if os.path.exists(tgt_dir):
                log.debug("Path '%s' exists in the filesystem", tgt_dir)
                if not os.path.isdir(tgt_dir):
                    raise NonDirFoundAtDirLocationError(
                        "Non-directory found where we want a directory ('%s')",
                        tgt_dir)
            else:
                log.debug("Creating directory '%s'", tgt_dir)
                if not opts.quiet:
                    print("D: %s" % fh.fpath)
                os.mkdir(tgt_dir, fh.mode)
                changed_contents = True

            # Dealing with a directory on the filesystem, not an fd - use the
            # regular os.*() variants, not the os.f*() methods.

            # Change modes and ownership.
            expect_uid = fh.uid
            expect_gid = fh.gid

            dstat = os.stat(tgt_dir)
            if dstat.st_uid != expect_uid or dstat.st_gid != expect_gid:
                changed_uidgid = True
                log.debug("Changing dir %s ownership to %s/%s",
                            tgt_dir, fh.user, fh.group)
                if not opts.quiet:
                    print("D: %s (user/group: %s/%s -> %s/%s)" % (fh.fpath,
                            dstat.st_uid, dstat.st_gid, expect_uid, expect_gid))
                os.chown(tgt_dir, expect_uid, expect_gid)

            if dstat.st_mode != fh.mode:
                changed_mode = True
                log.debug("Changing dir %s mode to %06o", tgt_dir, fh.mode)
                if not opts.quiet:
                    print("D: %s (mode: %06o -> %06o)" % (fh.fpath,
                            dstat.st_mode, fh.mode))
                os.chmod(tgt_dir, fh.mode)

            if changed_mode or changed_uidgid:
                opts.stats.directory_metadata_differed += 1


        # Update the client-side HSYNC.SIG data.
        log.debug("Updating dest hash for '%s'", fh.fpath)
        update_dest_filehash(fh)

    log.debug("fetch_needed(): done")

    if errorCount == 0:
        if not opts.quiet:
            print("Fetch completed")
        log.debug("Fetch completed successfully")
        return fetch_added

    else:
        log.warn("Fetch failed with %d errors", errorCount)
        return None


def delete_not_needed(not_needed, target, opts):
    '''
    Remove files from the destination that are not present on the source.
    '''
    dirs_to_delete = []
    error_count = 0

    for fh in not_needed:
        if fh.is_dir:
            log.debug("Saving dir '%s' for later deletion")
            dirs_to_delete.append(fh)

        else:
            fullpath = os.path.join(target, fh.fpath)
            log.debug("delete_not_needed: %s", fullpath)
            if not opts.quiet:
                print("Remove file: %s" % fh.fpath)
            try:
                os.remove(fullpath)
            except OSError as e:
                log.warn("Failed to remove file %s: %s", fh.fpath, e)
                error_count += 1

    if dirs_to_delete:
        # Sort the delete list by filename, then reverse so it's depth-
        # first.
        dirs_to_delete.sort(key=lambda x: x.fpath, reverse=True)
        for d in dirs_to_delete:
            fullpath = os.path.join(target, d.fpath)
            if not opts.quiet:
                print("Remove dir: %s" % d.fpath)
            log.debug("Deleting directory '%s'", fullpath)
            try:
                os.rmdir(fullpath)
            except OSError as e:
                log.warn("Failed to remove dir %s: %s", d.fpath, e)
                error_count += 1

    if error_count:
        log.warn("Delete failed with %d errors", error_count)
        return False

    return True


def fetch_contents(fpath, opts, root='', no_trim=False,
                    for_filehash=None, short_name=None,
                    file_count_number=None, file_count_total=None,
                    remote_flag=True, include_in_total=True):
    '''
    Wrap a fetch, which may be from a file or URL depending on the options.

    Returns None on a 404, re-raises the Exception otherwise.
    '''

    fullpath = fpath

    if not no_trim and opts.trim_path and root:
        fullpath = os.path.join(opt.source_url, fpath)

    log.debug("fetch_contents: %s", fullpath)

    fh = None
    if for_filehash is not None:
        fh = for_filehash

    # Try to get a friendly name.
    fname = fpath
    if short_name:
        fname = short_name
    elif fh is not None:
        fname = fh.fpath

    filecountstr = ''
    if file_count_number is not None:
        if file_count_total is not None:
            pct = 100.0*file_count_number/file_count_total
            filecountstr = ' [object %d/%d (%.0f%%)]' % (
                                                file_count_number,
                                                file_count_total,
                                                pct)
        else:
            filecountstr = ' [file %d]' % file_count_number

    # This part of the progress meter doesn't change, so cache it.
    pfx = "%s" % (filecountstr)

    if not opts.quiet:
        if opts.progress:
            progress_spacer = "\n\t"
            pfx = "\r" + pfx
        else:
            progress_spacer = ''

        print('F: %s%s%s' % (fname, progress_spacer, pfx), end='')

    outfile = ''
    progress = False

    try:
        if remote_flag and include_in_total:
            opts.stats.content_fetches += 1
        else:
            opts.stats.metadata_fetches += 1

        url = urllib2.urlopen(fullpath)
    except urllib2.HTTPError as e:
        if e.code == 404:
            resp = BaseHTTPRequestHandler.responses
            log.warn("Failed to retrieve '%s': %s", fullpath, resp[404][0])
            return None
        else:
            raise(e)

    size = 0
    size_is_known = False
    block_size = int(opts.fetch_blocksize)

    if fh is not None:
        size = fh.size
        size_is_known = True

    elif 'content-length' in url.info()['content-length']:
        size = int(url.info()['content-length'])
        size_is_known = True

    if opts.progress and size_is_known:
        progress = True
        sizestr = IEC.bytes_to_unit(size)

    bytes_read = 0
    more_to_read = True
    last_strlen = 0

    def progstr():
        if size_is_known:
            if size == 0:
                pct = 100.0     # Seems logical.
            else:
                pct = 100.0 * bytes_read / size

            print ("\r\t%s (file progress %s/%s [%.0f%%])" % (pfx,
                                IEC.bytes_to_unit(bytes_read),
                                sizestr,
                                pct),
                    end='')
        else:
            print("\r%s (download %s/unknown)" % (pfx,
                                IEC.bytes_to_unit(bytes_read)),
                    end='')


    if opts.progress:
        progstr()

    while more_to_read:
        # if log.isEnabledFor(logging.DEBUG):
        #     log.debug("Read: %d bytes (%d/%d)", block_size, bytes_read, size)
        try:
            new_bytes = url.read(block_size)
            if not new_bytes:
                more_to_read = False
            else:
                bytes_read += len(new_bytes)
                if remote_flag:
                    if include_in_total:
                        opts.stats.bytes_transferred += len(new_bytes)
                    else:
                        opts.stats.metadata_bytes_transferred += len(new_bytes)

                outfile += new_bytes
                if opts.progress:
                    progstr()

        except urllib2.URLError as e:
            log.warn("'%s' fetch failed: %s", str(e))
            raise e

    if not opts.progress:
        # In progress mode, give the caller a chance to add information.
        print('')

    if size_is_known and bytes_read != size:
        # That's an error. No need for a cryptochecksum to tell that.
        log.warn("'%s': Fetched %d bytes, expected %d bytes",
                    fname, bytes_read, size)
        return None

    return outfile


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
    recv.add_option("--no-delete", action="store_true",
        help="Never remove files from the destination, even if they're "
            "not present on the source")
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
    p.add_option_group(recv)

    recv.add_option("-U", "--signature-url",
        help="Specify the signature file's URL [default: <source_url>/HSYNC.SIG]")

    meta = optparse.OptionGroup(p, "Other options")
    meta.add_option("--version", action="store_true",
        help="Show the program version")
    meta.add_option("-V", "--verify-only", action="store_true",
        help="Verify only, do not transfer or delete files")
    meta.add_option("--fail-on-errors", action="store_true",
        help="Fail on any error. Default is to try to carry on")
    meta.add_option("-c", "--always-checksum", action="store_true",
        help="Always read and re-checksum files, never trust file modification"
            "times or other metadata")
    meta.add_option("--hash-file", default="HSYNC.SIG",
        help="Specify the hash filename [default: %default]")
    meta.add_option("--no-ignore-dirs", action="store_true",
        help="Don't trim common dirs such as .git, .svn and CVS")
    meta.add_option("--no-ignore-files", action="store_true",
        help="Don't trim common ignore-able files such as *~ and *.swp")
    meta.add_option("--no-trim-path", action="store_false",
        default=True, dest='trim_path',
        help="Don't trim the top-level path from filenames. It's safer to "
            "leave this well alone.")
    meta.add_option("-X", "--exclude-dir", action="append",
        help="Specify a directory path (relative to the root) to ignore. "
            "On the server side, this simply doesn't checksum the file, "
            "which has the effect of rendering it invisible (and deletable!)"
            "on the client side. On the client side, it prevents processing "
            "of the path.")
    meta.add_option("--fetch-blocksize", default=32*1000,
        help="Specify the number of bytes to retrieve at a time "
            "[default: %default]")
    # This is used to pass stats around the app.
    meta.add_option("--stats", help=optparse.SUPPRESS_HELP)

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

    if opt.quiet and (opt.verbose or opt.debug):
        log.error("It doesn't make sense to mix quiet and verbose options")
        return False

    level = logging.WARNING
    if opt.verbose:
        level = logging.INFO
    if opt.debug:
        level = logging.DEBUG
        opt.verbose = True

    logging.basicConfig(level=level)
    log = logging.getLogger()

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

    if not 'sha256' in hashlib.algorithms:
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
                                    os.path.dirname(up.path), '', '', ''])
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
