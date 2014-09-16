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

        self.copy_by_creation = False
        self.copy_by_copying = False
        self.size_comparison_valid = False

        self.ignore = False
        self.has_real_hash = False

        if S_ISDIR(mode):
            self.is_file = False
            self.is_dir = True
            self.copy_by_creation = True
            self.hashstr = self.blankhash[:]

        elif S_ISREG(mode):
            self.is_dir = False
            self.is_file = True
            self.hash_file()
            self.copy_by_copying = True
            self.has_real_hash = True
            self.size_comparison_valid = False

        else:
            self.is_dir = False
            self.is_file = False
            self.hashstr = self.blankhash[:]

        self.hash_safe = True
        return self


    @classmethod
    def init_from_string(cls, string, trim=False, root=''):
        self = cls()
        log.debug("ifs: %s", string)
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

        if S_ISDIR(mode):
            self.is_file = False
            self.is_dir = True
            self.copy_by_creation = True

        elif S_ISREG(mode):
            self.is_dir = False
            self.is_file = True
            self.has_real_hash = True
            self.copy_by_copying = True
            self.size_comparison_valid = True

        else:
            self.is_dir = False
            self.is_file = False
            self.hashstr = self.blankhash[:]

        self.hash_safe = True
        return self


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


    def __str__(self):
        return self.presentation_format()


    def __repr__(self):
        return "[FileHash: fullpath %s fpath %s size %d " \
                "mode %06o uid %d gid %d hashstr %s]" % (
                        self.fullpath, self.fpath,
                        self.size, self.mode,
                        self.uid, self.gid, self.hashstr)

