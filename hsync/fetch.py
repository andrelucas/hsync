# URL fetch.

from __future__ import print_function

from BaseHTTPServer import BaseHTTPRequestHandler
import hashlib
import logging
import os
import re
from random import SystemRandom
import sys
import urllib2
import urlparse

from numformat import IECUnitConverter
from stats import StatsCollector
from exceptions import *
from utility import is_path_included

log = logging.getLogger()


def fetch_contents(fpath, opts, root='', no_trim=False, for_filehash=None,
                   short_name=None, file_count_number=None,
                   file_count_total=None, remote_flag=True,
                   include_in_total=True):
    '''
    Wrap a fetch, which may be from a file or URL depending on the options.

    Returns None on a 404, re-raises the Exception otherwise.
    '''

    fullpath = fpath

    if not no_trim and opts.trim_path and root:
        fullpath = os.path.join(opts.source_url, fpath)

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
            if file_count_total == 0:
                pct = 100.0
            else:
                pct = 100.0 * file_count_number / file_count_total
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
    except urllib2.URLError as e:
        log.warn("Failed to retrieve '%s': %s", fullpath, e)
        return None

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
        sizestr = IECUnitConverter.bytes_to_unit(size)

    bytes_read = 0
    more_to_read = True

    def progstr():
        if size_is_known:
            if size == 0:
                pct = 100.0     # Seems logical.
            else:
                pct = 100.0 * bytes_read / size

            print ("\r\t%s (file progress %s/%s [%.0f%%])" %
                   (pfx,
                    IECUnitConverter.bytes_to_unit(
                        bytes_read),
                    sizestr,
                    pct),
                   end='')
        else:
            print("\r%s (download %s/unknown)" %
                  (pfx,
                   IECUnitConverter.bytes_to_unit(bytes_read)),
                  end='')

    if opts.progress:
        progstr()

    while more_to_read:
        # if log.isEnabledFor(logging.DEBUG):
        #     log.debug("Read: %d bytes (%d/%d)",
        #               block_size,bytes_read, size)
        try:
            new_bytes = url.read(block_size)
            nblen = len(new_bytes)
            if not new_bytes:
                more_to_read = False
            else:
                bytes_read += nblen
                if remote_flag:
                    if include_in_total:
                        opts.stats.bytes_transferred += nblen
                    else:
                        opts.stats.metadata_bytes_transferred += nblen

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


class FetchException(Exception):
    pass


class FetchContentsFailedException(FetchException):
    pass


class FetchFailedChecksumException(FetchException):
    pass


class FetchFatalException(Exception):
    pass


def fetch_needed(needed, source, opts):
    '''
    Download/copy the necessary files from opts.source_url or opts.source_dir
    to opts.dest_dir.

    This is a bit fiddly, as it tries hard to get the modes right.

    Returns a tuple (fetch_added, error_count), a list of FileHash objects we
    /added/ as a result of this run, and the number of errors in the run.
    '''

    r = SystemRandom()
    fetch_added = []
    error_count = 0

    if not source.endswith('/'):
        source += "/"

    counters = StatsCollector('FetchStats', [
        'contents_differ_count',
        'differing_file_index',
        'signature_checkpoint'
    ])
    counters.contents_differ_count = 0
    counters.differing_file_index = 0
    counters.signature_checkpoint = 0

    included_dirs = set()

    if opts.include:
        log.debug("Includes: %s", opts.include)
        re_globmatch = re.compile(r'[*?\[\]]')
        incset = set([d for d in opts.include if not re_globmatch.search(d)])
        incset_glob = set([d for d in opts.include if not d in incset])
    else:
        incset = set()
        incset_glob = set()

    # These are used to debug the -I filter.
    i_fetched = []
    i_not_fetched = []

    # Set up counters for the progress meter.
    for fh in needed:
        includeable = is_path_included(fh.fpath,
                                       incset, incset_glob,
                                       included_dirs,
                                       is_dir=fh.is_dir)

        if fh.dest_missing or fh.contents_differ:
            if not opts.include or includeable:
                if fh.is_file:
                    counters.contents_differ_count += 1

    # This is used to get current information into the destination
    # hashlist. That way, current information is written to the client
    # HSYNC.SIG, saving on re-scans.
    changed = StatsCollector('ChangeStatus',
                             ['contents', 'uidgid', 'mode', 'mtime'])

    for n, fh in enumerate(needed, start=1):

        if opts.include and not is_path_included(fh.fpath,
                                                 incset, incset_glob,
                                                 included_dirs,
                                                 is_dir=fh.is_dir):
            log.debug("Inclusion filter: '%s' is not included, skipping",
                      fh.fpath)
            i_not_fetched.append(fh)
            continue

        changed.contents = False
        changed.uidgid = False
        changed.mode = False
        changed.mtime = False

        if log.isEnabledFor(logging.DEBUG):
            if fh.is_dir:
                log.debug("fetch_needed: dir %s", fh.fpath)
            else:
                log.debug("fetch_needed: %s", fh.fpath)

        source_url = urlparse.urljoin(source, fh.fpath)

        success = False

        if fh.is_file:
            try:
                _file_fetch(fh, source_url, changed, counters, r, opts)
                success = True

            except FetchException as e:
                log.warn("Fetch file %s failed: %s", source_url, e)
                error_count += 1

        elif fh.is_link:
            try:
                _link_fetch(fh, changed, opts)
                success = True

            except FetchException as e:
                log.warn("Update link %s failed: %s", fh.fpath, e)
                error_count += 1

        elif fh.is_dir:
            try:
                _dir_fetch(fh, changed, opts)
                success = True

            except FetchException as e:
                log.warn("Update dir %s failed: %s", fh.fpath, e)
                error_count += 1

        # Update the client-side HSYNC.SIG data.
        if success:
            i_fetched.append(fh)
            log.debug("Updating dest hash for '%s'", fh.fpath)
            update_dest_filehash(fh, changed, fetch_added)
        else:
            i_not_fetched.append(fh)

    log.debug("fetch_needed(): done")

    if error_count == 0:
        if not opts.quiet:
            print("Fetch completed")
        log.debug("Fetch completed successfully")

    else:
        log.warn("Fetch completed with %d errors", error_count)

    if opts.fetch_debug:
        _fetch_debug(i_fetched, i_not_fetched)

    return (fetch_added, error_count)


def _fetch_debug(fetched, not_fetched, outfile=sys.stderr):
    print("XDEBUG BEGIN fetch i_fetched", file=outfile)
    for fh in fetched:
        print(fh._debug_repr(), file=outfile)
    print("XDEBUG END fetch i_fetched", file=outfile)

    print("XDEBUG BEGIN fetch i_not_fetched", file=outfile)
    for fh in not_fetched:
        print(fh._debug_repr(), file=outfile)
    print("XDEBUG END fetch i_not_fetched", file=outfile)


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
                log.warn("Failed to delete file %s: %s", fullpath, e)
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
                log.warn("Failed to delete dir %s: %s", fullpath, e)
                error_count += 1

    if error_count:
        log.warn("Delete failed with %d errors", error_count)
        return False

    return True


def update_dest_filehash(src_fh, changed, fetch_added):

    if src_fh.associated_dest_object is None:
        log.debug("Saved new file '%s' for inclusion in sigfile",
                  src_fh.fpath)
        fetch_added.append(src_fh)

    else:
        dst_fh = src_fh.associated_dest_object
        log.debug("Updating dest FileHash object for '%s", src_fh.fpath)

        if changed.contents:
            dst_fh.size = src_fh.size
            dst_fh.hashstr = src_fh.hashstr

        if changed.uidgid:
            dst_fh.uid = src_fh.uid
            dst_fh.gid = src_fh.gid

        if changed.mode:
            dst_fh.mode = src_fh.mode

        if changed.mtime:
            dst_fh.mtime = src_fh.mtime


def _file_fetch(fh, source_url, changed, counters, random, opts):

    tgt_file = os.path.join(opts.dest_dir, fh.fpath)
    tgt_file_rnd = tgt_file + ".%08x" % random.randint(0, 0xffffffff)

    if fh.dest_missing or fh.contents_differ:

        contents_differ = getattr(fh, 'contents_differ', False)
        counters.differing_file_index += 1

        opts.stats.file_contents_differed += 1

        log.debug("Fetching: '%s' dest_missing %s contents_differ %s",
                  fh.fpath, fh.dest_missing, contents_differ)

        if not opts.quiet and sys.stdout.isatty():
            print("F: %s\r" % fh.fpath, end='')

        # Fetch_contents will display progress information itself.
        contents = fetch_contents(
            source_url, opts,
            for_filehash=fh,
            file_count_number=counters.differing_file_index,
            file_count_total=counters.contents_differ_count)

        if contents is None:
            if opts.fail_on_errors:
                raise ContentsFetchFailedError(
                    "Failed to fetch '%s'" % source_url)
            else:
                log.debug("Failed to fetch '%s'",
                          fh.fpath)
                raise FetchContentsFailedException(
                    "Failed to fetch %s" % source_url)

        else:

            changed.contents = True  # If we fetched it, we changed it.

            chk = hashlib.sha256()
            log.debug("Hashing contents")

            if opts.progress:
                print(' checking...', end='')

            chk.update(contents)
            log.debug("Contents hash done (%s)", chk.hexdigest())

            if opts.progress:
                print('done')

            if chk.hexdigest() != fh.hashstr:
                log.warn("File '%s' failed checksum verification!",
                         fh.fpath)
                raise FetchFailedChecksumException(
                    "File %s failed checksum verification" % fh.fpath)

            log.debug("Will write to '%s'", tgt_file_rnd)
            if os.path.exists(tgt_file):
                if os.path.islink(tgt_file):
                    raise ParanoiaError(
                        "Not overwriting existing symlink '%s' with "
                        "file" % tgt_file)
                if os.path.isdir(tgt_file):
                    raise DirWhereFileExpectedError(
                        "Directory found where file expected at '%s'" %
                        tgt_file)

            # Dealing with file descriptors, use os.f*() variants.
            tgt = os.open(tgt_file_rnd,
                          os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                          fh.mode)
            if tgt == -1:
                raise OSOperationFailedError("Failed to open '%s'" %
                                             tgt_file_rnd)

            os.write(tgt, contents)
            os.close(tgt)
            log.debug("Moving into place: '%s' -> '%s'",
                      tgt_file_rnd, tgt_file)
            if os.rename(tgt_file_rnd, tgt_file) == -1:
                raise OSOperationFailedError(
                    "Failed to rename '%s' to '%s'" %
                    (tgt_file_rnd, tgt_file))

            expect_uid = fh.uid
            expect_gid = fh.gid

            filestat = os.stat(tgt_file)
            if filestat.st_uid != expect_uid or \
                    filestat.st_gid != expect_gid:
                changed.uidgid = True
                log.debug("Changing file %s ownership to %s/%s",
                          tgt_file, fh.user, fh.group)
                if os.chown(tgt_file, expect_uid, expect_gid) == -1:
                    log.warn("Failed to chown '%s' to user %s "
                             "group %s",
                             tgt_file, fh.user, fh.group)

            changed.mode = False  # We didn't change it, we created it.

            changed.mtime = True
            os.utime(tgt_file, (fh.mtime, fh.mtime))

            if changed.uidgid or changed.mtime or changed.mode:
                opts.stats.file_metadata_differed += 1

    elif fh.metadata_differs:

        log.debug("'%s': metadata differs", fh.fpath)

        expect_uid = fh.uid
        expect_gid = fh.gid

        filestat = os.stat(tgt_file)

        if not opts.quiet:
            print("F: %s" % (fh.fpath), end='')

        if filestat.st_uid != expect_uid or \
                filestat.st_gid != expect_gid:
            changed.uidgid = True
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
            changed.mode = True
            if not opts.quiet:
                print(" (mode %06o -> %06o)" %
                      (filestat.st_mode, fh.mode), end='')

            log.debug("'%s': Setting mode: %06o", fh.fpath, fh.mode)
            if os.chmod(tgt_file, fh.mode) == -1:
                log.warn("Failed to fchmod '%s' to %06o",
                         fh.fpath, fh.mode)

        if filestat.st_mtime != fh.mtime:
            changed.mtime = True
            if not opts.quiet:
                print(" (mtime %d -> %d)" %
                      (filestat.st_mtime, fh.mtime), end='')
            os.utime(tgt_file, (fh.mtime, fh.mtime))

        opts.stats.file_metadata_differed += 1

        if not opts.quiet:
            print('')

    elif fh.mtime_differs:
        log.debug("'%s': mtime differs", fh.fpath)
        changed.mtime = True

        if not opts.quiet:
            filestat = os.stat(tgt_file)
            print("F: %s (mtime %d -> %d)" % (fh.fpath,
                                              filestat.st_mtime, fh.mtime))

        os.utime(tgt_file, (fh.mtime, fh.mtime))
        opts.stats.file_metadata_differed += 1


def _link_fetch(fh, changed, opts):

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
                "Non-symlink found where we want a symlink ('%s')" %
                linkpath)

        else:
            # Symlink found. Check it.
            curtgt = os.readlink(linkpath)
            # Create or move the symlink.
            if curtgt != fh.link_target:
                changed.contents = True
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
        changed.uidgid = True
        log.debug("Changing link '%s' ownership to %s/%s",
                  linkpath, expect_uid, expect_gid)
        os.lchown(linkpath, expect_uid, expect_gid)

    if lstat.st_mode != fh.mode:
        changed.mode = True
        log.debug("Changing link '%s' mode to %06o",
                  linkpath, fh.mode)
        os.lchmod(linkpath, fh.mode)

    if changed.mode or changed.uidgid:
        opts.stats.link_metadata_differed += 1


def _dir_fetch(fh, changed, opts):

    tgt_dir = os.path.join(opts.dest_dir, fh.fpath)
    if os.path.exists(tgt_dir):
        log.debug("Path '%s' exists in the filesystem", tgt_dir)
        if not os.path.isdir(tgt_dir):
            raise NonDirFoundAtDirLocationError(
                "Non-directory found where directory expected ('%s')" %
                tgt_dir)
    else:
        log.debug("Creating directory '%s'", tgt_dir)
        if not opts.quiet:
            print("D: %s" % fh.fpath)
        os.makedirs(tgt_dir, fh.mode)
        changed.contents = True

    # Dealing with a directory on the filesystem, not an fd - use the
    # regular os.*() variants, not the os.f*() methods.

    # Change modes and ownership.
    expect_uid = fh.uid
    expect_gid = fh.gid

    dstat = os.stat(tgt_dir)
    if dstat.st_uid != expect_uid or dstat.st_gid != expect_gid:
        changed.uidgid = True
        log.debug("Changing dir %s ownership to %s/%s",
                  tgt_dir, fh.user, fh.group)
        if not opts.quiet:
            print("D: %s (user/group: %s/%s -> %s/%s)" %
                  (fh.fpath, dstat.st_uid, dstat.st_gid, expect_uid,
                   expect_gid))
        os.chown(tgt_dir, expect_uid, expect_gid)

    if dstat.st_mode != fh.mode:
        changed.mode = True
        log.debug("Changing dir %s mode to %06o", tgt_dir, fh.mode)
        if not opts.quiet:
            print("D: %s (mode: %06o -> %06o)" % (fh.fpath,
                                                  dstat.st_mode, fh.mode))
        os.chmod(tgt_dir, fh.mode)

    if changed.mode or changed.uidgid:
        opts.stats.directory_metadata_differed += 1
