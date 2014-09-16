#!/usr/bin/env python

import grp
import hashlib
import logging
import os.path
import pwd
import re
from stat import *
import sys

from idmapper import *
from exceptions import *

class NotHashableException(Exception): pass
class UnsupportedFileTypeException(Exception): pass
class LinkOperationOnNonLinkError(Exception): pass

class HashStringFormatError(Exception): pass
class BadSymlinkFormatError(HashStringFormatError): pass



log = logging.getLogger()

fileignore = [
    re.compile(r'(~|\.swp)$'),
]

dirignore = [
    re.compile(r'^(?:CVS|\.git|\.svn)'),
]

class FileHash(object):

    blankhash = "0" * 64

    # Class-wide cache of uid<->user and gid<->group mappings.
    mapper = UidGidMapper()

    def __init__(self):
        self.hash_safe = False


    @classmethod
    def init_from_file(cls, fpath, trim=False, root=''):
        self = cls()
        self.fullpath = fpath
        if trim:
            self.fpath = self.fullpath[len(root)+1:]
        else:
            self.fpath = self.fullpath
        self.stat = os.stat(self.fullpath)
        mode = self.mode = self.stat.st_mode
        self.uid = self.stat.st_uid
        self.user = self.mapper.get_name_for_uid(self.uid)
        self.gid = self.stat.st_gid
        self.group = self.mapper.get_name_for_gid(self.gid)
        self.size = self.stat.st_size
        self.mtime = self.stat.st_mtime

        # Safe defaults.
        self.copy_by_creation = False
        self.copy_by_copying = False
        self.size_comparison_valid = False
        self.is_file = self.is_dir = self.is_link = False
        self.ignore = False
        self.has_real_hash = False

        if S_ISDIR(mode):
            self.is_dir = True
            # It makes no sense to 'copy' remote filesystem metadata.
            self.copy_by_creation = True
            self.hashstr = self.blankhash[:]

        elif S_ISLNK(mode):
            self.is_link = True
            # Recreate symlinks, copy is unlikely to work as the target
            # (if it's a web server) will probably not send the link
            # contents, more likely it will send the target contents.
            self.copy_by_creation = True
            # Size comparison is not valid, we may be under a different-
            # length path, so the target will be a different length.
            self.has_real_hash = False
            # For the same reason, the hash is meaningless.
            self.hashstr = self.blankhash[:]

        elif S_ISREG(mode):
            self.is_file = True
            self.hash_file()
            self.copy_by_copying = True
            self.has_real_hash = True
            self.size_comparison_valid = False

        else:
            self.is_dir = False
            self.is_file = False
            self.hashstr = self.blankhash[:]
            raise UnsupportedFileTypeException(
                "%s: File type '%s' is unsupported" % 
                self._type_to_string(ftype))

        self.hash_safe = True
        return self


    @classmethod
    def init_from_string(cls, string, trim=False, root=''):
        self = cls()
        log.debug("init_from_string: %s", string)
        (md, smode, user, group, mtime, size, fpath) = string.split(None, 7)
        self.hashstr = md
        mode = self.mode = int(smode, 8)
        self.user = user
        self.uid = self.mapper.get_uid_for_name(user)
        self.group = group
        self.gid = self.mapper.get_gid_for_name(group)
        self.mtime = mtime
        self.size = int(size) # XXX int length?

        self.fpath = fpath

        opath = fpath
        if trim:
            opath = os.path.join(root, opath)
        self.fullpath = opath

        self.copy_by_creation = False
        self.copy_by_copying = False
        self.size_comparison_valid = False

        self.ignore = False
        self.has_real_hash = False

        self.is_dir = self.is_link = self.is_file = False

        if S_ISDIR(mode):
            self.is_dir = True
            self.copy_by_creation = True

        elif S_ISLNK(mode):
            self.is_link = True
            self.has_real_hash = True
            if not '>>>' in fpath:
                raise BadSymlinkFormatError(
                    "%s: Expected '>>>' in symlink hash" % fpath)
            (link,target) = fpath.split('>>>', 2)
            if not link or not target:
                raise BadSymlinkFormatError(
                    "%s: Bogus symlink hash" % fpath)
            target = target.lstrip() # Optional whitespace right of '>>>'.
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
                self._type_to_string(mode))

        self.hash_safe = True
        return self


    def _type_to_string(self, mode):
            ftype='UNKNOWN'
            if S_ISDIR(mode):
                ftype = 'dir'
            elif S_ISLNK(mode):
                ftype = 'symlink'
            elif S_ISREG(mode):
                ftype = 'file'
            elif S_ISCHR(mode) or S_ISBLK(mode):
                ftype='device'
            elif S_ISFIFO(mode):
                ftype='pipe'
            elif S_ISSOCK(mode):
                ftype='socket'
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
        return md


    def hash_file(self):
        log.debug("File: %s", self.fullpath)
        f = open(self.fullpath, 'rb').read() # Could read a *lot*.
        md = hashlib.sha256()
        md.update(f)
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
                       self.mtime, self.size,
                       self.fpath
                       )


    def can_compare(self, other):
        if self.has_real_hash and other.has_real_hash:
            return True
        else:
            return False
            

    def compare_contents(self, other):
        if not self.has_real_hash:
            raise NotHashableException("%s (lhs) isn't comparable" % self.fpath)
        if not other.has_real_hash:
            raise NotHashableException("%s (rhs) isn't comparable" % other.fpath)

        log.debug("compare_contents: %s, %s", self, other)
        return self.hashstr == other.hashstr


    def compare(self, other, ignore_uid_gid=False, ignore_mode=False):
        '''
        Thorough object identity check. Return True if files are the same,
        otherwise False.
        '''

        if log.isEnabledFor(logging.DEBUG):
            log.debug("compare: self %s other %s", repr(self), repr(other))

        if self.size_comparison_valid and self.size != other.size:
            log.debug("Object sizes differ")
            return False

        if not ignore_mode:
            if self.mode != other.mode:
                log.debug("Object modes differ")
                return False

        if not ignore_uid_gid:
            if self.uid != other.uid:
                log.debug("Object UIDs differ")
                return False
            if self.gid != other.gid:
                log.debug("Object GIDs differ")
                return False

        if self.can_compare(other):
            if not self.compare_contents(other):
                log.debug("Hash verification failed")
                return False
            else:
                log.debug("Hash verified")

        log.debug("Identity check pass")
        return True


    def compare_link(self, selfpath, other, otherpath):
        '''
        Symlink compare is a little trickier. We need the paths in which our
        links are embedded in order to compare their targets.
        '''

        us = localise_link_target(self, selfpath)
        them = localise_link_target(other, otherpath)
        log.debug("compare_link: us '%s' them '%s'", us, them)
        return us == them


    def localise_link_target(self, selfpath):
        '''
        Return our link target relative to selfpath. If we're under selfpath,
        strip selfpath. Otherwise, return the whole path.

        Will throw an exception if we're not a symlink.
        '''
        if not S_ISLNK(self.mode):
            raise LinkOperationOnNonLinkError("'%s' is not a symlink",
                                                self.fpath)
        # log.debug("localise_link_target: '%s' selfpath '%s'",
        #             self.link_target, selfpath)

        topdir = selfpath
        if not topdir.endswith(os.sep):
            topdir += os.sep

        if self.link_target.startswith(topdir):
            tpath = self.link_target[len(topdir):]
            log.debug("Normalise: %s -> %s (topdir %s)",
                        self.link_target, tpath, topdir)
            return tpath
        else:
            return self.link_target



    def __str__(self):
        return self.presentation_format()


    def __repr__(self):
        return "[FileHash: fullpath %s fpath %s size %d " \
                "mode %06o uid %d gid %d hashstr %s]" % (
                        self.fullpath, self.fpath,
                        self.size, self.mode,
                        self.uid, self.gid, self.hashstr)




