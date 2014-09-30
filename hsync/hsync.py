#!/usr/bin/env python

# Simple sync-in-the-clear tool. Use SHA* and http to sync two
# directories using only HTTP GET.

from __future__ import print_function

from BaseHTTPServer import BaseHTTPRequestHandler
import grp
import hashlib
import logging
import optparse
import os.path
import pwd
from random import SystemRandom
import re
from stat import *
from cStringIO import StringIO
import sys
import urllib2
import urlparse

from exceptions import *
from filehash import *
from idmapper import *
from numformat import IECUnitConverter as IEC
from stats import StatsCollector


log = logging.getLogger()

class URLMustBeOfTypeFileError(Exception): pass
class ContentsFetchFailedError(Exception): pass
class TruncatedHashfileError(Exception): pass


def hashlist_generate(srcpath, opts, source_mode=True, existing_hashlist=None):
    '''
    Generate the hashlist for the given path.

    srcpath - the top-level directory
    opts    - the optparse options dict

    Return a list of FileHash objects representing objects in the srcpath
    filesystem.

    If opts.trim_path is True, strip the srcpath from the filename in the
    hashlist. This makes it easier to work with relative paths.

    opts.no_ignore_dirs and opts.no_ignore_files disable the default
    behaviour, which is to ignore of common dirs (CVS, .git, .svn) and files
    (*~, *.swp).

    '''

    log.debug("hashlist_generate: srcpath %s source_mode %s", 
                srcpath, source_mode)
    if os.path.exists(srcpath):
        if not os.path.isdir(srcpath):
            raise NonDirFoundAtDirLocationError(
                "'%s' found but is not a directory" % srcpath)
    else:
        os.mkdir(srcpath)

    # If we're the target, defer reading file contents until we're asked to
    # compare. That way, if we're trusting the mtime, we may not have to read
    # the file at all.
    if opts.always_checksum:
        defer_fs_read = False
    else:
        defer_fs_read = True

    lookup_existing = None
    source_extramsg = ''

    # If we have an existing hashfile, also defer reading the file, as we may
    # be able to avoid that if we trust mtimes.
    if existing_hashlist is not None:
        lookup_existing = hashlist_to_dict(existing_hashlist)
        defer_fs_read = True
        source_extramsg = ' (using pre-existing hash to reduce IO)'

    hashlist = []

    if not opts.quiet:
        if source_mode:
            print("Scanning source filesystem%s" % (source_extramsg))
        else:
            print("Comparing local filesystem to signature file%s" %
                    (source_extramsg))

    if opts.progress and source_mode:
        verb="Add"
    else:
        verb="Scan"

    for root, dirs, files in os.walk(srcpath):

        if log.isEnabledFor(logging.DEBUG):
            logging.debug("os.walk: root %s dirs %s files %s", root, dirs, files)

        dirs.sort()

        # See if the directory list can be pruned.
        if not opts.no_ignore_dirs:
            for dirname in dirs:
                for di in dirignore:
                    if di.search(dirname):
                        if source_mode and opts.verbose:
                            print("Skipping ignore-able dir %s" % dirname)
                        dirs.remove(dirname)

        # Likewise, handle the user's exclusions.
        if opts.exclude_dir:
            done_skip = False
            for dirname in opts.exclude_dir:
                if dirname in dirs:
                    if source_mode and opts.verbose:
                        print("Skipping manually-excluded dir %s" % dirname)
                    log.debug("Exclude dir '%s'", dirname)
                    dirs.remove(dirname)
                    done_skip=True
            if done_skip:
                log.debug("dirs now %s", dirs)

        # Handle directories.
        for n, dirname in enumerate(dirs, start=1):
            fpath = os.path.join(root, dirname)
            fh = FileHash.init_from_file(fpath, trim=opts.trim_path,
                                            root=srcpath,
                                            defer_read=defer_fs_read)
            if opts.progress:
                print("D: %s dir %s (dir-in-dir %d/%d)" % (verb, fpath, n, len(dirs)))
            elif opts.verbose:
                print("%s dir: %s" % (verb, fpath))
            hashlist.append(fh)

        files.sort()
            
        for n, filename in enumerate(files, start=1):

            fpath = os.path.join(root, filename)

            if filename == opts.hash_file:
                log.debug("Skipping pre-existing hash file '%s'", opts.hash_file)
                continue

            skipped = False
            if not opts.no_ignore_files:
                for fi in fileignore:
                    if fi.search(fpath):
                        if source_mode and opts.verbose:
                            print("Ignore:  %s" % fpath)
                        skipped = True
                        break

            if skipped:
                continue

            log.debug("Add file: %s", fpath)

            if opts.progress:
                print("F: %s [dir %s] file %s (file-in-dir %d/%d)" %
                                (verb, root, filename, n, len(files)))
            elif opts.verbose:
                print("%s file: %s" % (verb, fpath))

            fh = FileHash.init_from_file(fpath, trim=opts.trim_path, root=srcpath,
                                            defer_read=defer_fs_read)

            if not opts.always_checksum and fh.is_file:
                # Attempt to bypass the checksum, if the old HSYNC.SIG has it.
                do_checksum = True

                if lookup_existing is not None:
                    if fh.fpath in lookup_existing:
                        oldfh = lookup_existing[fh.fpath]
                        log.debug("'%s': Found old entry (%s)", fh.fpath, repr(oldfh))
                        if fh.safe_to_skip(oldfh):
                            do_checksum = False
                            fh.inherit_attributes(oldfh)

                if do_checksum:
                    log.debug("'%s': fall back to reading file", fh.fpath)
                    fh.read_file_contents()

            log.debug("'%s': Adding to hash list", fh.fpath)
            assert fh.hashstr != fh.notsethash
            hashlist.append(fh)

    log.debug("hashlist_generate: entries %d", len(hashlist))
    return hashlist


def sigfile_write(hashlist, abs_path, opts,
                    use_tmp=False, verb='Generating'):

    if not opts.quiet:
        print("%s signature file %s" % (verb, abs_path))

    log.debug("Sorting signature file")
    hashlist.sort(key=lambda fh: fh.fpath)

    if use_tmp:
        r = SystemRandom()
        abs_path_tmp = abs_path + ".%08x" % r.randint(0, 0xffffffff)
        log.debug("Writing temporary hash file '%s'", abs_path_tmp)
        sigfile = open(abs_path_tmp, 'w')

    else:
        log.debug("Writing hash file '%s'", abs_path)
        sigfile = open(abs_path, 'w')

    for fh in hashlist:
        assert fh.hashstr != fh.notsethash, \
            "Hash should not be the 'not set' value"
        print(fh.presentation_format(), file=sigfile)
    print("FINAL: %s" % (hash_of_hashlist(hashlist)), file=sigfile)
    sigfile.close()

    if use_tmp:
        log.debug("Moving hashfile into place: '%s' -> '%s'",
                    abs_path_tmp, abs_path)
        if os.rename(abs_path_tmp, abs_path) == -1:
            raise OSOperationFailedError("Failed to rename '%s' to '%s'",
                                        abs_path_tmp, abs_path)

    return True


def hash_of_hashlist(hashlist):
    '''
    Take a created hashlist and hash its digests and paths, to get
    a composite hash.
    '''

    md = hashlib.sha256()
    for fh in hashlist:
        md.update(fh.sha_hash().digest())

    return md.hexdigest()


def hashlist_to_dict(hashlist):
    '''
    Take a hashlist generated by generate_hashlist(), and return a dict keyed
    on the file path, with the hash as the value.
    '''
    log.debug("hashlist_to_dict: Creating lookup hash")
    hdict = {}
    for fh in hashlist:
        hdict[fh.fpath] = fh

    #log.debug("hdict %s", hdict)
    return hdict


def hashlist_from_stringlist(strfile, opts, root=None):

    hashlist = []
    for l in strfile:
        if l.startswith("#"):
            pass # FFR
        if l.startswith("FINAL: "):
            pass # FFR
        else:
            fh = FileHash.init_from_string(l, opts.trim_path, root=root)
            hashlist.append(fh)
    
    return hashlist


def hashlist_check(dstpath, src_hashlist, opts, existing_hashlist=None,
                    opportunistic_write=False, opwrite_path=None):
    '''
    Check the dstpath against the provided hashlist.

    Return a tuple (needed, notneeded, dst_hashlist), where needed is a list
    of filepaths that need to be fetched, and notneeded is a list of filepaths
    that are not present on the target, so may be removed. dst_hashlist is
    a list of FileHash objects for the destination path.

    '''

    src_fdict = hashlist_to_dict(src_hashlist)
    
    # Take the simple road. Generate a hashlist for the destination.
    dst_hashlist = hashlist_generate(dstpath, opts, source_mode=False,
                                        existing_hashlist=existing_hashlist)

    if opportunistic_write:
        assert opwrite_path is not None
        sigfile_write(dst_hashlist, opwrite_path, opts,
                        use_tmp=True, verb='Caching scanned')

    dst_fdict = hashlist_to_dict(dst_hashlist)

    direx = set()
    if opts.exclude_dir:
        direx = set(opts.exclude_dir)

    # Now compare the two dictionaries.
    needed = []
    excluded_dirs = set()

    mapper = UidGidMapper()
    if opts.set_user:
        mapper.set_default_name(opts.set_user)
    if opts.set_group:
        mapper.set_default_group(opts.set_group)


    for fpath, fh in [(k,src_fdict[k]) for k in sorted(src_fdict.keys())]:

        exclude = False

        # Generate (pointless) stat.
        if not fh.is_dir and fh.size_is_known:
            opts.stats.bytes_total += fh.size

        # Process exclusions.
        if fh.is_dir and fpath in direx:
            log.debug("%s: Exclude dir", fpath)
            dpath = fpath.rstrip(os.sep) + os.sep # Make sure it ends in a slash.
            excluded_dirs.add(dpath)
            log.debug("Added exclusion dir: '%s'", dpath)
            exclude = True

        if not exclude: # No point checking twice.
            for exc in excluded_dirs:
                if fpath.startswith(exc):
                    log.debug("Excluded '%s': Under '%s'", fpath, exc)
                    exclude = True

        if exclude:
            continue

        # If the user overrode stuff, set that up here.
        if opts.set_user:
            fh.uid = mapper.default_uid
            fh.user = mapper.default_name

        if opts.set_group:
            fh.gid = mapper.default_gid
            fh.group = mapper.set_default_group

        if fpath in dst_fdict:

            if not src_fdict[fpath].compare(dst_fdict[fpath],
                                    ignore_mode=opts.ignore_mode,
                                    trust_mtime=(not opts.always_checksum)):
                log.debug("%s: needed", fpath)
                # Store a reference to the object at the destination.
                # This can be used to update the dest's HSYNC.SIG file and save
                # on rechecks.
                fh.associated_dest_object = dst_fdict[fpath]
                needed.append(fh)                

        else:
            log.debug("%s: needed", fpath)
            fh.dest_missing = True
            needed.append(fh)
                
    not_needed = []
    for fpath, fh in dst_fdict.iteritems():
        if not fpath in src_fdict:
            log.debug("%s: not found in source", fpath)
            not_needed.append(fh)

    return (needed, not_needed, dst_hashlist)




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

                if not opts.quiet:
                    print("F: %s" % fh.fpath, end='')

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
    errorCount = 0

    for fh in not_needed:
        if fh.is_dir:
            log.debug("Saving dir '%s' for later deletion")
            dirs_to_delete.append(fh)

        else:
            fullpath = os.path.join(target, fh.fpath)
            log.debug("delete_not_needed: %s", fullpath)
            if not opts.quiet:
                print("Remove file: %s" % fh.fpath)
            os.remove(fullpath)

    if dirs_to_delete:
        # Sort the delete list by filename, then reverse so it's depth-
        # first.
        dirs_to_delete.sort(key=lambda x: x.fpath, reverse=True)
        for d in dirs_to_delete:
            fullpath = os.path.join(target, d.fpath)
            if not opts.quiet:
                print("Remove dir: %s" % d.fpath)
            log.debug("Deleting directory '%s'", fullpath)
            os.rmdir(fullpath)

    if errorCount:
        log.warn("Delete failed with %d errors", errorCount)
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

        print('\rF: %s%s%s' % (fname, progress_spacer, pfx), end='')

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


def _cano_url(url, slash=False):
    log.debug("_cano_url: %s", url)
    up = urlparse.urlparse(url)
    log.debug("urlparse: %s", up.geturl())
    if up.scheme == '':
        url = 'file://' + url
        log.debug("Add scheme, URL=%s", url)
    if slash and not url.endswith("/"):
        url += "/"
    return url


def source_side(opt, args):

    # If there's an existing hashfile, optionally use it to try to reduce the
    # amount of scanning.

    abs_hashfile = None
    
    if opt.signature_url:
        hashurl = _cano_url(opt.signature_url)
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

        abs_hashfile = os.path.join(opt.source_dir, hashfile)
        log.debug("Synthesised hash file location: '%s'", abs_hashfile)

    existing_hl = None

    if not opt.always_checksum and os.path.exists(abs_hashfile):
        if not opt.quiet:
            print("Reading existing hashfile")

        # Fetch the signature file.
        hashfile_contents = fetch_contents('file://' + abs_hashfile, opt, short_name=opt.hash_file)
        strfile = hashfile_contents.splitlines()
        existing_hl = hashlist_from_stringlist(strfile, opt, root=opt.source_dir)

    hashlist = hashlist_generate(opt.source_dir, opt, existing_hashlist=existing_hl)
    if hashlist is not None:

        if not sigfile_write(hashlist, abs_hashfile, opt, use_tmp=True):
            log.error("Failed to write signature file '%s'",
                os.path.join(opt.source_dir, opt.hash_file))
            return False
        
        return True

    else:
        log.error("Send-side generate failed")
        return False


def dest_side(opt, args):

    if opt.source_url is None:
        log.error("-u/--source-url must be defined for -D/--dest-dir mode")
        return False

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
        raise Exception("Explicit proxy not yet implemented")
        
    hashurl = None
    if opt.signature_url:
        hashurl = _cano_url(opt.signature_url)
        log.debug("Explicit signature URL '%s'", hashurl)

    else:
        hashurl = _cano_url(opt.source_url, slash=True) + opt.hash_file
        log.debug("Synthesised signature URL '%s'", hashurl)

    # Fetch the signature file.
    if not opt.quiet:
        print("Fetching remote hashfile")
    hashfile_contents = fetch_contents(hashurl, opt,
                                        short_name=opt.hash_file, 
                                        include_in_total=False)

    if hashfile_contents is None:
        # We're not coming back from this.
        log.error("Failed to retrieve signature file from '%s", hashurl)
        return False

    src_strfile = hashfile_contents.splitlines()
    if not src_strfile[-1].startswith("FINAL:"):
        raise TruncatedHashfileError("'FINAL:'' line of hashfile %s appears to be missing!" % hashurl)

    src_hashlist = hashlist_from_stringlist(src_strfile, opt, root=opt.dest_dir)

    opt.source_url = _cano_url(opt.source_url, slash=True)
    log.debug("Source url '%s", opt.source_url)

    abs_hashfile = os.path.join(opt.dest_dir, opt.hash_file)
    existing_hl = None

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
                                            opwrite_path=abs_hashfile)

    if opt.verify_only:
        # Give a report if we're verbose.
        if opt.verbose:
            for fh in needed:
                print("Needed: %s" % fh.fpath)
            for fh in not_needed:
                print("Needs delete: %s" % fh.fpath)

        if needed or not_needed:
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
                                        use_tmp=True, verb='Writing'):
                log.error("Failed to write signature file '%s'",
                            os.path.join(opt.source_dir, opt.hash_file))
                return False

        if opt.verbose:
            print('%s' % opt.stats)

        return True


def getopts(cmdargs):

    p = optparse.OptionParser()

    send = optparse.OptionGroup(p, "Send-side options")
    send.add_option("-S", "--source-dir",
        help="Specify the source directory")
    p.add_option_group(send)

    recv = optparse.OptionGroup(p, "Receive-side options")
    recv.add_option("-D", "--dest-dir",
        help="Specify the destination directory")
    recv.add_option("-u", "--source-url",
        help="Specify the data source URL")
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
