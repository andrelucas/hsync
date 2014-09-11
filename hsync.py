#!/usr/bin/env python

# Simple sync-in-the-clear tool. Use SHA* and http to sync two
# directories using only HTTP GET.


import grp
import hashlib
import logging
import optparse
import os.path
import pwd
from random import SystemRandom
import re
from stat import *
import sys
import urllib
import urlparse

log = logging.getLogger()

fileignore = [
    re.compile(r'(~|\.swp)$'),
]

dirignore = [
    re.compile(r'^(?:CVS|\.git|\.svn)'),
]

class UidGidMapper(object):

    uid_to_name = {}
    name_to_uid = {}
    gid_to_name = {}
    name_to_gid = {}

    def get_name_for_uid(self, uid):
        if not uid in self.uid_to_name:
            name = pwd.getpwuid(uid).pw_name
            self.uid_to_name[uid] = name
            self.name_to_uid[name]  = uid
        return self.uid_to_name[uid]

    
    def get_name_for_gid(self, gid):
        if not gid in self.gid_to_name:
            name = grp.getgrgid(gid).gr_name
            self.gid_to_name[gid] = name
            self.name_to_gid[name] = gid
        return self.gid_to_name[gid]


    def get_uid_for_name(self, name):
        if not name is self.name_to_uid:
            uid = pwd.getpwnam(name).pw_uid
            self.name_to_uid[name] = uid
            self.uid_to_name[uid] = name
        return self.name_to_uid[name]


    def get_gid_for_name(self, group):
        if not group in self.name_to_gid:
            gid = grp.getgrnam(group).gr_gid
            self.name_to_gid[group] = gid
            self.gid_to_name[gid] = group
        return self.name_to_gid[group]


class NotHashableException(Exception): pass

class FileHash(object):

    blankhash = "0" * 64

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

        self.ignore = False
        self.has_real_hash = False

        if S_ISDIR(mode):
            self.is_file = False
            self.is_dir = True
            self.hashstr = self.blankhash[:]

        elif S_ISREG(mode):
            self.is_dir = False
            self.is_file = True
            self.hash_file()
            self.has_real_hash = True

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
        (md, smode, user, group, fpath) = string.split(None, 5)
        self.hashstr = md
        mode = self.mode = int(smode, 8)
        self.user = user
        self.group = group
        self.fpath = fpath
        opath = fpath
        if trim:
            opath = os.path.join(root, opath)
        self.fullpath = opath

        self.ignore = False
        self.has_real_hash = False

        if S_ISDIR(mode):
            self.is_file = False
            self.is_dir = True

        elif S_ISREG(mode):
            self.is_dir = False
            self.is_file = True
            self.has_real_hash = True

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
        logging.info("Hash for %s: %s", self.fpath, md.hexdigest())
        self.contents_hash = md.digest()
        self.hashstr = md.hexdigest()



    def presentation_format(self):
        return "%s %06o %s %s %s" % (
                       self.hashstr, self.mode,
                       self.user, self.group, self.fpath
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


    def __str__(self):
        return self.presentation_format()


    def __repr__(self):
        return "[FileHash: fullpath %s fpath %s hashstr %s]" % (
                        self.fullpath, self.fpath, self.hashstr)


def hashlist_generate(srcpath, opts):
    '''
    Generate the haslist for the given path.

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

    if not os.path.isdir(srcpath):
        log.error("Source '%s' is not a directory", srcpath)
        return False

    hashlist = []

    for root, dirs, files in os.walk(srcpath):

        if log.isEnabledFor(logging.DEBUG):
            logging.debug("os.walk: root %s dirs %s files %s", root, dirs, files)

        # See if the directory list can be pruned.
        if not opts.no_ignore_dirs:
            for dirname in dirs:
                for di in dirignore:
                    if di.search(dirname):
                        log.info("Skipping ignore-able dir '%s'", dirname)
                        dirs.remove(dirname)

        # Handle directories.
        for dirname in dirs:
            fpath = os.path.join(root, dirname)
            fh = FileHash.init_from_file(fpath, trim=opts.trim_path, root=srcpath)
            hashlist.append(fh)
            
        for filename in files:

            fpath = os.path.join(root, filename)
            skipped = False
            if not opts.no_ignore_files:
                for fi in fileignore:
                    if fi.search(fpath):
                        log.info("Skipping ignore-able file '%s'", fpath)
                        skipped = True
                        break

            if skipped:
                continue

            if os.path.islink(fpath):
                log.warn("Ignoring symbolic link '%s'", fpath) # XXX is this right?
                continue

            log.debug("File: %s", fpath)
            fh = FileHash.init_from_file(fpath, trim=opts.trim_path, root=srcpath)

            hashlist.append(fh)

    return hashlist


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
    hdict = {}
    for fh in hashlist:
        hdict[fh.fpath] = fh

    log.debug("hdict %s", hdict)
    return hdict


def hashlist_from_stringlist(strfile, opts):

    hashlist = []
    for l in strfile:
        if l.startswith("FINAL: "):
            pass # XXX
        else:
            fh = FileHash.init_from_string(l, opts.trim_path, root=opts.dest_dir)
            hashlist.append(fh)
    
    return hashlist


def hashlist_check(dstpath, src_hashlist, opts):
    '''
    Check the dstpath against the provided hashlist.

    Return a tuple (needed, notneeded), where needed is a list of filepaths
    that need to be fetched, and notneeded is a list of filepaths that are
    not present on the target, so may be removed.
    '''
    
    src_fdict = hashlist_to_dict(src_hashlist)
    
    # Take the simple road. Generate a hashlist for the destination.
    dst_hashlist = hashlist_generate(dstpath, opts)
    dst_fdict = hashlist_to_dict(dst_hashlist)

    # Now compare the two dictionaries.

    needed = []

    for fpath, fh in [(k,src_fdict[k]) for k in sorted(src_fdict.keys())]:

        if fpath in dst_fdict:
            if src_fdict[fpath].can_compare(dst_fdict[fpath]):
                if src_fdict[fpath].compare_contents(dst_fdict[fpath]):
                    log.debug("%s: present and hash verified", fpath)
                else:
                    log.debug("%s: present but failed hash verify", fpath)
                    needed.append(fh)
            else:
                # Couldn't verify contents, assume it's needed.
                log.debug("%s: present, can't compare - assume needed", fpath)
                needed.append(fh)
                

        else:
            log.debug("%s: needed", fpath)
            needed.append(fh)
                
    not_needed = []
    for fpath, fh in dst_fdict.iteritems():
        if not fpath in src_fdict:
            log.debug("%s: not found in source", fpath)
            not_needed.append(fh)
        
    return (needed, not_needed)

class DirWhereFileExpectedError(Exception): pass
class NonDirFoundAtDirLocationError(Exception): pass
class OSOperaationFailedError(Exception): pass
class ParanoiaError(Exception): pass


def fetch_needed(needed, source, opts):
    '''
    Download/copy the necessary files from opts.source_url or opts.source_dir
    to opts.dest_dir.

    This is a bit fiddly, as it tries hard to get the modes right.
    '''

    r = SystemRandom()
    mapper = UidGidMapper()

    if not source.endswith('/'):
        source += "/"

    for fh in needed:
        log.debug("fetch_needed: %s", fh.fpath)
        source_url = urlparse.urljoin(source, fh.fpath)
        if fh.is_file:
            contents = fetch_contents(source_url, opts)
            tgt_file = os.path.join(opts.dest_dir, fh.fpath)
            tgt_file_rnd = tgt_file + ".%08x" % r.randint(0, 0xfffffffff)
            log.debug("Will write to '%s'", tgt_file_rnd)
            if os.path.exists(tgt_file):
                if os.path.islink(tgt_file):
                    raise ParanoiaError(
                        "Not overwriting existing symlink '%s' with file", tgt_file)
                if os.path.isdir(tgt_file):
                    raise DirWhereFileExpectedError(
                        "Directory found where file expected at '%s'", tgt_file)

            tgt = os.open(tgt_file_rnd, os.O_CREAT | os.O_EXCL | os.O_WRONLY, fh.mode)
            if tgt == -1:
                raise OSOperationFailedError("Failed to open '%s'", tgt_file_rnd)

            expect_uid = mapper.get_uid_for_name(fh.user)
            expect_gid = mapper.get_gid_for_name(fh.group)
            filestat = os.stat(tgt_file_rnd)
            if filestat.st_uid != expect_uid or filestat.st_gid != expect_gid:
                log.debug("Changing file %s ownership to %s/%s",
                            tgt_file_rnd, fh.user, fh.group)
                if os.fchown(tgt, expect_uid, expect_gid) == -1:
                    log.warn("Failed to fchown '%s' to user %s group %s",
                            tgt_file_rnd, fh.user, fh.group)

            os.write(tgt, contents)
            os.close(tgt)
            log.debug("Moving into place: '%s' -> '%s'", tgt_file_rnd, tgt_file)
            if os.rename(tgt_file_rnd, tgt_file) == -1:
                raise OSOperationFailedError("Failed to rename '%s' to '%s'",
                    tgt_file_rnd, tgt_file)

        elif fh.is_dir:
            tgt_dir = os.path.join(opts.dest_dir, fh.fpath)
            if os.path.exists(tgt_dir):
                log.debug("Directory '%s' found", tgt_dir)
                if not os.path.isdir(tgt_dir):
                    raise NonDirFoundAtDirLocationError(
                        "Non-directory found where we want a directory ('%s')",
                        tgt_dir)
            else:
                log.debug("Creating directory '%s'", tgt_dir)
                if os.mkdir(tgt_dir, fh.mode) == -1:
                    raise OSOperationFailedError("Failed to mkdir(%s)", tgt_dir)

            # Change modes and ownership.
            expect_uid = mapper.get_uid_for_name(fh.user)
            expect_gid = mapper.get_gid_for_name(fh.group)
            dstat = os.stat(tgt_dir)
            if dstat.st_uid != expect_uid or dstat.st_gid != expect_gid:
                log.debug("Changing dir %s ownership to %s/%s",
                            tgt_dir, fh.user, fh.group)
                if os.fchown(tgt_dir, expect_uid, expect_gid) == -1:
                        log.warn("Failed to fchmod '%s' to user %s group %s",
                            tgt_dir, fh.user, fh.group)
            if dstat.st_mode != fh.mode:
                log.debug("Changing dir %s mode to %06o", tgt_dir, fh.mode)
                if os.fchmod(tgt_dir, fh.mode) == -1:
                    raise OSOperationFailedError("Failed to fchmod('%s', %06o)",
                                                tgt_dir, fh.mode)
                
                

def delete_not_needed(not_needed, target, opts):
    '''
    Remove files from the destination that are not present on the source.
    '''
    for fh in not_needed:
        # XXX directory delete
        fullpath = os.path.join(target, fh.fpath)
        log.debug("delete_not_needed: %s", fullpath)
        os.remove(fullpath)


def fetch_contents(fpath, opts, root='', no_trim=False):
    '''
    Wrap a fetch, which may be from a file or URL depending on the options.

    May also need a proxy.
    '''

    fullpath = fpath

    if not no_trim and opts.trim_path and root:
        fullpath = os.path.join(opt.source_url, fpath)

    log.debug("fetch_contents: %s", fullpath)
    contents = urllib.urlopen(fullpath).read()
    return contents


if __name__ == '__main__':

    p = optparse.OptionParser()

    send = optparse.OptionGroup(p, "Send-side options")
    send.add_option("-S", "--source-dir",
        help="Specify the source directory")
    p.add_option_group(send)

    recv = optparse.OptionGroup(p, "Receive-side options")
    recv.add_option("-D", "--dest-dir",
        help="Specify the destination directory")
    recv.add_option("-u", "--source-url",
        help="Specify the source URL")
    p.add_option_group(recv)

    meta = optparse.OptionGroup(p, "Other options")
    meta.add_option("--hash-file", default="HSYNC.SIG",
        help="Specify the hash filename [default: %default]")
    meta.add_option("--no-ignore-dirs", action="store_true",
        help="Don't trim common dirs such as .git, .svn and CVS")
    meta.add_option("--no-ignore-files", action="store_true",
        help="Don't trim common ignore-able files such as *~ and *.swp")
    meta.add_option("-t", "--trim-path", action="store_true",
        help="Trim the top-level path from output filenames")
    meta.add_option("-v", "--verbose", action="store_true",
        help="Enable verbose output")
    meta.add_option("-d", "--debug", action="store_true",
        help="Enable debugging output")
    p.add_option_group(meta)

    (opt, args) = p.parse_args()

    level = logging.WARNING
    if opt.verbose:
        level = logging.INFO
    if opt.debug:
        level = logging.DEBUG
    logging.basicConfig(level=level)
    log = logging.getLogger()

    if opt.source_dir and opt.dest_dir:
        log.error("Send-side and receive-side options can't be mixed")
        sys.exit(1)

    if log.isEnabledFor(logging.DEBUG):
        log.debug("hashlib.algorithms: %s", hashlib.algorithms)

    if not 'sha256' in hashlib.algorithms:
        log.error("No SHA256 implementation in hashlib!")
        sys.exit(1)

    # Send-side.
    if opt.source_dir:

        hashlist = hashlist_generate(opt.source_dir, opt)
        if hashlist is not None:
            sigfilename = os.path.join(opt.source_dir, opt.hash_file)
            sigfile = open(sigfilename, 'w')
            for fh in hashlist:
                print >>sigfile, fh.presentation_format()
            print >>sigfile, "FINAL: %s" % (hash_of_hashlist(hashlist))
            sigfile.close()
            sys.exit(0)

        else:
            log.error("Send-side generate failed")
            sys.exit(1)

    # Receive-side.
    if opt.dest_dir:
        hashurl = opt.source_url
        if not hashurl.endswith("/"):
            hashurl += "/"
        hashurl = urlparse.urljoin(hashurl, opt.hash_file)
        log.debug("Will fetch hashes from %s", hashurl)
        strfile = fetch_contents(hashurl, opt).splitlines()

        src_hashlist = hashlist_from_stringlist(strfile, opt)
        (needed, not_needed) = hashlist_check(opt.dest_dir, src_hashlist, opt)

        fetch_needed(needed, opt.source_url, opt)
        delete_not_needed(not_needed, opt.dest_dir, opt)
        
