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

import hashlib
import logging
import os.path
import re
from stat import *

from idmapper import *
from exceptions import *

log = logging.getLogger()


class NotHashableException(Exception):
    pass


class UnsupportedFileTypeException(Exception):
    pass


class LinkOperationOnNonLinkError(Exception):
    pass


class PathMustBeAbsoluteError(Exception):
    pass


class SymlinkPointsOutsideTreeError(Exception):
    pass


class ContentsReadOnNonFileError(Exception):
    pass


class HashStringFormatError(Exception):
    pass


class BadSymlinkFormatError(HashStringFormatError):
    pass


fileignore = [
    re.compile(r'(~|\.swp)$'),
    re.compile(r'\.nfs[0-9a-f]+$'),
]

dirignore = [
    re.compile(r'^(?:CVS|\.git|\.svn)'),
]


class FileHash(object):

    blankhash = "0" * 64
    notsethash = "F" * 64

    # Class-wide cache of uid<->user and gid<->group mappings.
    mapper = UidGidMapper()

    def __init__(self):
        self.hash_safe = False
        self.associated_dest_object = None
        self.size_is_known = False

    @classmethod
    def init_from_file(cls, fpath, trim=False, root='', defer_read=False):

        self = cls()
        self.is_local_file = True

        if not root.endswith("/"):
            root += "/"

        if log.isEnabledFor(logging.DEBUG):
            log.debug("init_from_file: '%s' trim=%s root='%s' defer_read=%s",
                      fpath, trim, root, defer_read)

        self.fullpath = fpath
        self.defer_read = defer_read
        self.has_read_contents = False

        if log.isEnabledFor(logging.DEBUG):
            log.debug("iff(): fullpath '%s'", self.fullpath)

        if trim:
            self.fpath = self.fullpath[len(root):]
        else:
            self.fpath = self.fullpath
        self.stat = os.lstat(self.fullpath)
        mode = self.mode = self.stat.st_mode
        self.uid = self.stat.st_uid
        self.user = self.mapper.get_name_for_uid(self.uid)
        self.gid = self.stat.st_gid
        self.group = self.mapper.get_group_for_gid(self.gid)
        self.size = self.stat.st_size
        self.size_is_known = True
        self.mtime = int(self.stat.st_mtime)

        # Safe defaults.
        self.copy_by_creation = False
        self.copy_by_copying = False
        self.size_comparison_valid = False
        self.is_file = self.is_dir = self.is_link = False
        self.ignore = False
        self.dest_missing = False  # Makes sense for a real fs object.
        self.has_real_hash = False

        if S_ISDIR(mode):
            self.is_dir = True
            # It makes no sense to 'copy' remote filesystem metadata.
            self.copy_by_creation = True
            self.hashstr = self.blankhash[:]

        elif S_ISLNK(mode):
            self.is_link = True
            log.debug("Reading symlink '%s'", self.fullpath)
            self.link_target = os.readlink(self.fullpath)
            log.debug("Symlink '%s' -> '%s'", self.fullpath, self.link_target)
            # Recreate symlinks, copy is unlikely to work as the target
            # (if it's a web server) will probably not send the link
            # contents, more likely it will send the target contents.
            self.copy_by_creation = True
            # Size comparison is not valid, we may be under a different-
            # length path, so the target will be a different length.
            self.has_real_hash = False
            # For the same reason, the hash is meaningless.
            self.hashstr = self.blankhash[:]
            self.link_normalised = False

            if root:
                self.normalise_symlink(root)

        elif S_ISREG(mode):
            self.is_file = True
            if defer_read:
                self.hashstr = self.notsethash
            else:
                self.read_file_contents()

            self.copy_by_copying = True
            self.has_real_hash = True
            self.size_comparison_valid = False

        else:
            self.is_dir = False
            self.is_file = False
            self.hashstr = self.blankhash[:]
            raise UnsupportedFileTypeException(
                "%s: File type '%s' is unsupported" %
                (self.fullpath, self._type_to_string(mode)))

        self.strhash_value = self.hash_value = None
        self.hash_safe = True
        return self

    @classmethod
    def init_from_string(cls, string, trim=False, root=''):

        self = cls()
        self.is_local_file = False

        if log.isEnabledFor(logging.DEBUG):
            log.debug("init_from_string: %s", string)

        (md, smode, user, group, mtime, size, fpath) = string.split(None, 6)
        self.hashstr = md
        mode = self.mode = int(smode, 8)
        self.user = user
        self.uid = self.mapper.get_uid_for_name(user)
        self.group = group
        self.gid = self.mapper.get_gid_for_group(group)
        # Robustness principle - old versions have float mtime.
        self.mtime = int(float(mtime))
        self.size = int(size)  # XXX int length?
        self.size_is_known = True

        self.fpath = fpath

        opath = fpath
        if trim:
            opath = os.path.join(root, opath)
        self.fullpath = opath

        self.copy_by_creation = False
        self.copy_by_copying = False
        self.size_comparison_valid = False

        self.ignore = False
        self.dest_missing = True  # Safe default.
        # self.contents_differ = False
        self.has_real_hash = False

        self.is_dir = self.is_link = self.is_file = False

        if S_ISDIR(mode):
            self.is_dir = True
            self.copy_by_creation = True

        elif S_ISLNK(mode):
            self.is_link = True
            self.has_real_hash = True
            if '>>>' not in fpath:
                raise BadSymlinkFormatError(
                    "%s: Expected '>>>' in symlink hash" % fpath)
            (link, target) = fpath.split('>>>', 1)
            if not link or not target:
                raise BadSymlinkFormatError(
                    "%s: Bogus symlink hash" % fpath)
            target = target.lstrip()  # Optional whitespace right of '>>>'.
            self.fpath = link
            self.link_target = target
            # Size comparisons are not valid because we are likely to be
            # copied into a different-length path, implying that the link
            # target has different length.
            self.has_real_hash = False
            # For the same reason, the hash is meaningless.
            self.hashstr = self.blankhash[:]
            # For the same reason again, we just create links.
            self.copy_by_creation = True
            if root:
                self.normalise_symlink(root)

        elif S_ISREG(mode):
            self.is_file = True
            self.has_real_hash = True
            self.copy_by_copying = True
            self.size_comparison_valid = True

        else:
            self.is_dir = False
            self.is_file = False
            self.hashstr = self.blankhash[:]
            raise UnsupportedFileTypeException(
                "%s: File type '%s' is unsupported" %
                (self.fullpath, self._type_to_string(mode)))

        self.strhash_value = self.hash_value = None
        self.hash_safe = True
        return self

    def read_file_contents(self):

        if not self.is_file:
            raise UnsupportedFileTypeException(
                "%s: Attempt to read contents of non-file" % self.fullpath)

        log.debug("Reading file '%s' contents", self.fullpath)
        self.hash_file()
        self.has_read_contents = True

    def safe_to_skip(self, other):
        '''
        Determine if we are sufficiently similar to FileHandle object other
        to avoid reading the file again.
        '''
        log.debug("'%s': skip check", self.fpath)
        if self.fpath != other.fpath:
            log.debug("names differ, fail skip check")
            return False
        if self.size != other.size:
            log.debug("sizes differ, fail skip check")
            return False
        if self.mtime != other.mtime:
            log.debug("mtimes differ, fail skip check")
            return False
        log.debug("skip check pass")
        return True

    def inherit_attributes(self, other):
        '''
        Copy attributes from another FileHandle object, in an attempt to
        save on IO. Don't copy stuff we don't need to.

        '''
        log.debug("inherit_attributes('%s'): grabbing hash", self.fpath)
        self.hashstr = other.hashstr
        self.has_read_contents = True

    def _type_to_string(self, mode):
        ftype = 'UNKNOWN'
        if S_ISDIR(mode):
            ftype = 'dir'
        elif S_ISLNK(mode):
            ftype = 'symlink'
        elif S_ISREG(mode):
            ftype = 'file'
        elif S_ISCHR(mode) or S_ISBLK(mode):
            ftype = 'device'
        elif S_ISFIFO(mode):
            ftype = 'pipe'
        elif S_ISSOCK(mode):
            ftype = 'socket'
        return ftype

    def sha_hash(self):
        '''
        Provide a stable hash for this object.
        '''
        assert self.hash_safe, "Hash available"
        md = hashlib.sha256()
        md.update(self.fpath)
        md.update(str(self.mode))
        md.update(self.user)
        md.update(self.group)
        md.update(self.hashstr)
        return md.hexdigest()

    def hash_file(self):
        log.debug("File: %s", self.fullpath)
        block_size = 10 * 1000 * 1000
        f = open(self.fullpath, 'rb')
        md = hashlib.sha256()

        while True:
            data = f.read(block_size)
            if not data:
                break
            md.update(data)

        log.debug("Hash for %s: %s", self.fpath, md.hexdigest())
        self.contents_hash = md.digest()
        self.hashstr = md.hexdigest()

    def presentation_format(self):
        fpath = self.fpath
        if self.is_link:
            fpath += '>>> %s' % self.link_target

        return "%s %06o %s %s %s %s %s" % (
            self.hashstr, self.mode,
            self.user, self.group,
            int(self.mtime), self.size,
            fpath)

    def can_compare(self, other):
        if self.has_real_hash and other.has_real_hash:
            return True
        else:
            return False

    def compare_contents(self, other):
        if not self.has_real_hash:
            raise NotHashableException(
                "%s (lhs) isn't comparable" % self.fpath)
        if not other.has_real_hash:
            raise NotHashableException(
                "%s (rhs) isn't comparable" % other.fpath)

        log.debug("compare_contents: %s, %s", self, other)
        return self.hashstr == other.hashstr

    def compare(self, other,
                ignore_name=False,
                ignore_uid_gid=False,
                ignore_mode=False,
                trust_mtime=True):
        '''
        Thorough object identity check. Return True if files are the same,
        otherwise False.
        '''

        # Since we're comparing, let's assume the remote at least has the
        # file.
        self.dest_missing = False

        differ_name = False
        differ_metadata = False
        differ_contents = False
        differ_mtime = False
        mtime_skip = False

        if log.isEnabledFor(logging.DEBUG):
            log.debug("compare: self %s other %s ignore_uid_gid %s "
                      "ignore_mode %s trust_mtime %s",
                      repr(self), repr(other),
                      ignore_uid_gid, ignore_mode, trust_mtime)

        if not ignore_name:
            if self.fpath != other.fpath:
                log.debug("Object names differ")
                differ_name = True

        if self.size_comparison_valid and self.size != other.size:
            log.debug("Object sizes differ")

        if not ignore_mode:
            if self.mode != other.mode:
                log.debug("Object modes differ")
                differ_metadata = True

        if not ignore_uid_gid:
            if self.uid != other.uid:
                log.debug("Object UIDs differ")
                differ_metadata = True
            if self.gid != other.gid:
                log.debug("Object GIDs differ")
                differ_metadata = True

        # If enabled, check the mtime and if it matches, consider ourselves
        # done.
        if trust_mtime:
            if self.mtime == other.mtime:
                log.debug("'%s': mtime match, assuming ok", self.fpath)
                mtime_skip = True
            else:
                log.debug("'%s': mtime mismatch, will check", self.fpath)
                differ_mtime = True

        if not mtime_skip:
            # If we're a local file, we may be able to save some time.
            if self.is_local_file:
                if self.defer_read and not self.has_contents():
                    self.hash_file()
                    self.has_read_contents = True

            if self.can_compare(other):
                if not self.compare_contents(other):
                    log.debug("Hash verification failed")
                    differ_contents = True
                else:
                    log.debug("Hash verified")

        log.debug("'%s': Identity check: name %s contents %s metadata %s "
                  "mtime %s", self.fpath, differ_name, differ_contents,
                  differ_metadata, differ_mtime)

        self.contents_differ = differ_contents
        self.metadata_differs = differ_metadata
        self.mtime_differs = differ_mtime

        differs = differ_contents or differ_metadata or \
            differ_mtime or differ_name
        return not differs

    def normalise_symlink(self, root):
        '''
        Given a root directory, make symlinks that point inside our tree
        relative, and mark links that point outside the tree as external.
        '''
        if not S_ISLNK(self.mode):
            raise LinkOperationOnNonLinkError("'%s' is not a symlink" %
                                              self.fpath)
        log.debug("normalise_symlink: %s", repr(self))

        self.link_normalised = True
        self.link_relpath = self.source_symlink_make_relative(srcdir=root)

        if self.link_relpath.startswith(os.sep):
            log.warn("'%s' (symlink to '%s') points outside the tree - "
                     "normalising to '%s'",
                     self.fpath, self.link_target, self.link_relpath)
            self.link_target = self.link_relpath
            self.link_is_external = True
        else:
            self.link_is_external = False

    def source_symlink_make_relative(self, srcdir, absolute_is_error=False):
        '''
        On the source side, find if a symlink is under srcdir, and
        if it is, make it relative. If not, make it absolute.

        Returns the best path we can make. If it starts with a '/', it's
        absolute and so is out of the tree.

        If absolute_is_error, throw an Error for non-absolute results.

        srcdir must be absolute. We need to start somewhere.

        Throws an Error if not a symlink.
        '''

        if not srcdir.startswith(os.sep):
            raise PathMustBeAbsoluteError(
                "'%s' must be an absolute path" % srcdir)

        if not S_ISLNK(self.mode):
            raise LinkOperationOnNonLinkError("'%s' is not a symlink" %
                                              self.fpath)
        log.debug("source_symlink_make_relative: %s, %s",
                  self.fpath, self.link_target)

        topdir = os.path.normpath(srcdir)
        if not topdir.endswith(os.sep):
            topdir += os.sep

        tpath = self.link_target

        spath_full = os.path.join(topdir, self.fpath)
        norm_spath_full = os.path.normpath(spath_full)

        norm_lpath_full = os.path.dirname(norm_spath_full)
        # This is the location of the symlink (dirname fpath) plus the link
        # target.
        tpath_full = os.path.join(topdir, norm_lpath_full, self.link_target)
        norm_tpath_full = os.path.normpath(tpath_full)
        # norm_tpath_full)

        if norm_tpath_full.startswith(topdir):
            # We're under the source path -> relative link.
            tpath_rel = os.path.relpath(norm_tpath_full, norm_lpath_full)
            log.debug("link relative: '%s' -> '%s'", tpath_full, tpath_rel)
            return tpath_rel

        else:
            if absolute_is_error:
                raise SymlinkPointsOutsideTreeError(
                    "'%s' points outside the file tree "
                    "('%s', normalised to '%s') "
                    "and absolute links are disabled" %
                    (self.fpath, self.link_target, norm_tpath_full))

            # We're not under the source path -> absolute link.
            log.debug("link cannot be made relative : '%s' -> '%s'",
                      tpath, norm_tpath_full)
            return norm_tpath_full

    def __str__(self):
        return self.presentation_format()

    def __repr__(self):
        if self.is_link:
            fpath = '%s>>>%s' % (self.fpath, self.link_target)
        else:
            fpath = self.fpath
        return "[FileHash: fullpath %s fpath %s size %d " \
            "mode %06o mtime %d uid %d gid %d hashstr %s]" % (
                self.fullpath, fpath,
                self.size, self.mode,
                self.mtime,
                self.uid, self.gid, self.hashstr)

    def _debug_repr(fh):
        # Convenient debugging representation.
        return ','.join([fh.fpath, '%06o' % fh.mode, str(fh.mtime),
                         fh.user, fh.group, str(fh.size)])

    # These comparisons are for the purposes of object storage. They're
    # not effective for comparing the files when determining whether or
    # not to copy them; use compare() for that.

    def hash(self):
        if self.hash_value is None:
            self.hash_value = (self.fullpath, self.size, self.mode,
                               self.mtime, self.uid, self.gid, self.hashstr)
        return self.hash_value

    def strhash(self):
        if self.strhash_value is None:
            h = hashlib.md5(str(self.hash()))
            self.strhash_value = h.digest().encode('base64')
        return self.strhash_value

    def __hash__(self):
        return self.strhash()

    def __eq__(self, other):
        return self.hash() == other.hash()
