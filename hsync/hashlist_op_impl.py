# Hashlist operations.

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
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
# THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import print_function

import gzip
import logging
import os
from random import SystemRandom
import re
import sys

from exceptions import *
from filehash import *
from hashlist import *
from utility import is_dir_excluded, is_path_pre_excluded, is_hashfile

log = logging.getLogger()


def hashlist_generate(srcpath, opts, source_mode=True,
                      existing_hashlist=None):
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
        source_extramsg = ' (with cache)'

    hashlist = HashList()

    if not opts.quiet:
        if source_mode:
            print("Scanning source filesystem%s" % (source_extramsg))
        else:
            print("Comparing local filesystem to signature file%s" %
                  (source_extramsg))

    if opts.progress and source_mode:
        verb = "Add"
    else:
        verb = "Scan"

    re_globmatch = re.compile(r'[*?\[\]]')

    if opts.exclude_dir:
        excdirs = set([d for d in opts.exclude_dir
                       if not re_globmatch.search(d)])
        excdirs_glob = set([d for d in opts.exclude_dir
                            if d not in excdirs])
    else:
        excdirs = set()

    ##
    # Walk the filesystem.
    ##
    for root, dirs, files in os.walk(srcpath):

        relroot = root[len(srcpath) + 1:]

        if log.isEnabledFor(logging.DEBUG):
            log.debug("os.walk: root %s dirs %s files %s",
                      root, dirs, files)

        # See if the directory list can be pruned.
        # XXX refactor.

        if not opts.no_ignore_dirs:

            copydirs = dirs[:]  # Don't iterate over a list we may change.

            for dirname in copydirs:
                fulldirname = os.path.join(relroot, dirname)
                for di in dirignore:
                    # dirignore is a regex anchored to the start - need to
                    # use the short dirname, e.g. 'CVS', as opposed to the
                    # long dirname, 'stuff/CVS'.
                    if di.search(dirname):
                        if source_mode and opts.verbose:
                            print("Skipping ignore-able dir %s" % dirname)
                        dirs.remove(dirname)
                        log.debug("Exclude dir '%s' full path '%s'",
                                  dirname, fulldirname)

        # Likewise, handle the user's exclusions. This makes the assumption
        # that the list of exclusions will not be much larger than the list of
        # directories.

        if opts.exclude_dir:
            done_skip = False
            # Don't iterate over a list we'll be changing inside the loop.
            copydirs = dirs[:]
            for dirname in copydirs:
                fulldirname = os.path.join(relroot, dirname)

                if is_dir_excluded(fulldirname, excdirs, excdirs_glob):
                    log.debug("Exclude dir '%s' full path '%s'",
                              dirname, fulldirname)
                    dirs.remove(dirname)
                    done_skip = True

            if done_skip:
                log.debug("dirs now %s", dirs)

        # Handle directories.
        for n, dirname in enumerate(dirs, start=1):
            fpath = os.path.join(root, dirname)
            fh = FileHash.init_from_file(fpath, trim=opts.trim_path,
                                         root=srcpath,
                                         defer_read=defer_fs_read)
            if opts.progress:
                print("D: %s dir %s (dir-in-dir %d/%d)" %
                      (verb, fpath, n, len(dirs)))
            elif opts.verbose:
                print("%s dir: %s" % (verb, fpath))
            hashlist.append(fh)

        files.sort()

        for n, filename in enumerate(files, start=1):

            fpath = os.path.join(root, filename)

            # Don't include hashfiles or lockfiles.
            if is_hashfile(filename, custom_hashfile=opts.hash_file):
                log.debug("Skipping hash file or lock '%s'", filename)
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

            fh = FileHash.init_from_file(fpath, trim=opts.trim_path,
                                         root=srcpath,
                                         defer_read=defer_fs_read)

            if not opts.always_checksum and fh.is_file:
                # Attempt to bypass the checksum, if the old HSYNC.SIG has it.
                do_checksum = True

                if lookup_existing is not None:
                    if fh.fpath in lookup_existing:
                        oldfh = lookup_existing[fh.fpath]
                        log.debug("'%s': Found old entry (%s)",
                                  fh.fpath, repr(oldfh))
                        if fh.safe_to_skip(oldfh):
                            do_checksum = False
                            fh.inherit_attributes(oldfh)

                if do_checksum:
                    log.debug("'%s': fall back to reading file", fh.fpath)
                    fh.read_file_contents()

            log.debug("'%s': Adding to hash list", fh.fpath)
            assert fh.hashstr != fh.notsethash
            hashlist.append(fh)

    if opts.scan_debug:
        _scan_debug(hashlist)

    log.debug("hashlist_generate: entries %d", len(hashlist))
    return hashlist


def _scan_debug(hashlist, outfile=sys.stderr):
    print("XDEBUG BEGIN scan", file=outfile)
    for fh in hashlist:
        print(fh._debug_repr(), file=outfile)
    print("XDEBUG END scan", file=outfile)


def sigfile_write(hashlist, abs_path, opts,
                  use_tmp=False, verb='Generating', no_compress=False):

    compress = False
    if not no_compress:
        if opts.compress_signature is not None and \
                opts.compress_signature:
            compress = True

    assert not (compress and not use_tmp), \
        "Compression must be via a temp file"

    if not opts.quiet:
        print("%s signature file %s compress %s" %
              (verb, abs_path, compress))

    log.debug("Sorting signature file")
    # hashlist.sort(key=lambda fh: fh.fpath)
    hashlist.sort_by_path()

    writemode = 'w'

    if use_tmp:
        r = SystemRandom()
        abs_path_tmp = abs_path + ".%08x" % r.randint(0, 0xffffffff)
        log.debug("Writing temporary hash file '%s'", abs_path_tmp)
        sigfile = open(abs_path_tmp, writemode)

    else:
        log.debug("Writing hash file '%s'", abs_path)
        sigfile = open(abs_path, writemode)

    for fh in hashlist:
        assert fh.hashstr != fh.notsethash, \
            "Hash should not be the 'not set' value"
        print(fh.presentation_format(), file=sigfile)

    print("FINAL: %s" % (hash_of_hashlist(hashlist)), file=sigfile)
    sigfile.close()

    if use_tmp:
        log.debug("Moving hashfile into place: '%s' -> '%s'",
                  abs_path_tmp, abs_path)

        if compress:
            log.debug("Compressing hashfile '%s' to '%s'",
                      abs_path_tmp, abs_path)
            f_in = open(abs_path_tmp, 'r')
            f_out = gzip.open(abs_path, 'wb')
            f_out.writelines(f_in)
            f_out.close()
            f_in.close()
            log.debug("Removing temp hashfile '%s'", abs_path_tmp)
            os.unlink(abs_path_tmp)

        else:
            if os.rename(abs_path_tmp, abs_path) == -1:
                raise OSOperationFailedError("Failed to rename '%s' to '%s'",
                                             abs_path_tmp, abs_path)

    return True


def hash_of_hashlist(hashlist):
    '''
    Take a created hashlist and hash its digests and paths, to get
    a composite hash.
    '''

    log.debug("hash_of_hashlist(): start")
    md = hashlib.sha256()
    for fh in hashlist:
        md.update(fh.sha_hash())

    log.debug("hash_of_hashlist(): end")
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

    # log.debug("hdict %s", hdict)
    return hdict


def hashlist_from_stringlist(strfile, opts, root=None):

    log.debug("hashlist_from_stringlist():")
    hashlist = HashList()
    for l in strfile:
        if l.startswith("#"):
            pass  # FFR
        if l.startswith("FINAL: "):
            pass  # FFR
        else:
            fh = FileHash.init_from_string(l, opts.trim_path, root=root)
            fname = os.path.basename(fh.fullpath)
            if is_hashfile(fname, opts.hash_file):
                log.debug("Skipping hash or lock file %s", fh.fullpath)
            else:
                hashlist.append(fh)

    return hashlist


def hashlist_check(dstpath, src_hashlist, opts, existing_hashlist=None,
                   opportunistic_write=False, opwrite_path=None,
                   source_side=False):
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

    no_compress = False
    if source_side:
        no_compress = True

    if opportunistic_write:
        assert opwrite_path is not None
        sigfile_write(dst_hashlist, opwrite_path, opts,
                      use_tmp=True, verb='Caching scanned',
                      no_compress=no_compress)

    dst_fdict = hashlist_to_dict(dst_hashlist)

    re_globmatch = re.compile(r'[*?\[\]]')

    if opts.exclude_dir:
        direx = set([d for d in opts.exclude_dir
                     if not re_globmatch.search(d)])
        direx_glob = set([d for d in opts.exclude_dir
                          if d not in direx])
    else:
        direx = set()
        direx_glob = set()

    # Now compare the two dictionaries.
    needed = []
    excluded_dirs = set()

    mapper = UidGidMapper()
    if opts.set_user:
        mapper.set_default_name(opts.set_user)
    if opts.set_group:
        mapper.set_default_group(opts.set_group)

    for fpath, fh in [(k, src_fdict[k]) for k in sorted(src_fdict.keys())]:

        # Generate (pointless) stat.
        if not fh.is_dir and fh.size_is_known:
            opts.stats.bytes_total += fh.size

        assert fpath == fh.fpath

        # Process exclusions.
        if is_path_pre_excluded(fpath, excluded_dirs):
            continue

        if fh.is_dir:
            if is_dir_excluded(fpath, direx, direx_glob, excluded_dirs):
                log.debug("Dir '%s' excluded", fpath)
                continue

        # If the user overrode stuff, set that up here.
        if opts.set_user:
            fh.uid = mapper.default_uid
            fh.user = mapper.default_name

        if opts.set_group:
            fh.gid = mapper.default_gid
            fh.group = mapper.default_group

        if fpath in dst_fdict:

            if not src_fdict[fpath].compare(dst_fdict[fpath],
                                            ignore_mode=opts.ignore_mode,
                                            trust_mtime=(
                                                not opts.always_checksum)):
                log.debug("%s: needed", fpath)
                # Store a reference to the object at the destination.
                # This can be used to update the dest's HSYNC.SIG file and
                # save on rechecks.
                fh.associated_dest_object = dst_fdict[fpath]
                needed.append(fh)

        else:
            log.debug("%s: needed", fpath)
            fh.dest_missing = True
            needed.append(fh)

    not_needed = []
    for fpath, fh in dst_fdict.iteritems():
        if fpath not in src_fdict:
            log.debug("%s: not found in source", fpath)
            not_needed.append(fh)

    if opts.check_debug:
        _check_debug(needed, not_needed)

    return (needed, not_needed, dst_hashlist)


def _check_debug(needed, not_needed, outfile=sys.stderr):
    print("XDEBUG BEGIN check needed", file=outfile)
    for fh in needed:
        print(fh._debug_repr(), file=outfile)
    print("XDEBUG END check needed", file=outfile)

    print("XDEBUG BEGIN check not_needed", file=outfile)
    for fh in not_needed:
        print(fh._debug_repr(), file=outfile)
    print("XDEBUG END check not_needed", file=outfile)
