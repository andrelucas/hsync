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

from __future__ import print_function

import inspect
import cPickle as pickle
import os
import shutil
import time
import unittest

from hsync.idmapper import *
from hsync.filehash import *


class FileHashCreateFromFilesystemTestCase(unittest.TestCase):

    me = inspect.getfile(inspect.currentframe())
    topdir = os.path.join(os.path.dirname(me), 'test')

    mapper = UidGidMapper()

    @classmethod
    def setUpClass(self):
        self.user = self.mapper.get_name_for_uid(os.getuid())
        self.group = self.mapper.get_group_for_gid(os.getgid())

    def tearDown(self):
        if hasattr(self, 'tmp') and self.tmp:
            shutil.rmtree(self.tmp, True)

    def test_create_from_file(self):
        '''Creation from file is safe'''
        FileHash.init_from_file('/etc/hosts', root='/etc/', defer_read=True)

    def test_hash_file_contents(self):
        '''Hashing a file seems to work'''
        fname = os.path.join(self.topdir, 'f1')
        contents = 'OSSIFRAGE'
        f = open(fname, 'w')
        print(contents, file=f, end='')
        f.close()
        self.assertTrue(os.path.isfile(fname))

        md = hashlib.sha256()
        md.update(contents)
        testhash = md.hexdigest()

        fh = FileHash.init_from_file(fname, root=self.topdir, defer_read=True)
        fh.hash_file()
        self.assertEquals(fh.hashstr, testhash, "Hash is as expected")
        os.unlink(fname)

    def test_read_file_contents(self):
        '''Reading a file's contents updates the hash'''
        fname = os.path.join(self.topdir, 'f1')
        contents = 'OSSIFRAGE'
        f = open(fname, 'w')
        print(contents, file=f, end='')
        f.close()
        self.assertTrue(os.path.isfile(fname))

        md = hashlib.sha256()
        md.update(contents)
        testhash = md.hexdigest()

        fh = FileHash.init_from_file(fname, root=self.topdir, defer_read=True)
        fh.read_file_contents()
        self.assertEquals(fh.hashstr, testhash, "Hash is as expected")
        os.unlink(fname)

    def test_create_from_dir(self):
        '''Creation from dir is safe'''
        FileHash.init_from_file('/tmp', root='/', defer_read=True)

    def test_create_from_link(self):
        '''Creation from link is safe'''
        fname = os.path.join(self.topdir, 'f1')
        lname = os.path.join(self.topdir, 'l1')

        for fn in (lname, fname):
            try:
                os.unlink(fn)
            except OSError:
                pass

        f = open(fname, 'w')
        print('hello', file=f)
        f.close()
        os.symlink(fname, lname)
        self.assertTrue(os.path.isfile(fname))
        self.assertTrue(os.path.islink(lname))

        FileHash.init_from_file(lname, root=self.topdir, defer_read=True)

        for fn in (lname, fname):
            os.unlink(fn)

    def test_create_from_device(self):
        '''Should not allow creation from device node'''
        with self.assertRaises(UnsupportedFileTypeException):
            FileHash.init_from_file('/dev/zero', root='/dev', defer_read=True)

    def test_create_from_socket(self):
        '''Should not allow creation from device node'''
        with self.assertRaises(UnsupportedFileTypeException):
            FileHash.init_from_file('/dev/zero', root='/dev', defer_read=True)


class FileHashCreateFromStringTestCase(unittest.TestCase):

    me = inspect.getfile(inspect.currentframe())
    topdir = os.path.join(os.path.dirname(me), 'test')

    mapper = UidGidMapper()

    @classmethod
    def setUpClass(self):
        self.user = self.mapper.get_name_for_uid(os.getuid())
        self.group = self.mapper.get_group_for_gid(os.getgid())

    def tearDown(self):
        if hasattr(self, 'tmp') and self.tmp:
            shutil.rmtree(self.tmp, True)

    def test_create_as_file(self):
        '''Init a file from string form'''
        fstr = '0 100644 %s %s %s 100 /etc/hosts' % \
            (self.user, self.group, time.time())
        fh = FileHash.init_from_string(fstr, root='/etc')
        self.assertTrue(fh.is_file)
        self.assertFalse(fh.is_dir)
        self.assertFalse(fh.is_link)
        self.assertTrue(fh.size, 100)

    def test_create_as_dir(self):
        '''Init a dir from string form'''
        fstr = '0 040755 %s %s %s 0 /etc' % \
            (self.user, self.group, time.time())
        fh = FileHash.init_from_string(fstr, root='/')
        self.assertFalse(fh.is_file)
        self.assertTrue(fh.is_dir)
        self.assertFalse(fh.is_link)
        self.assertEquals(fh.size, 0)

    def test_create_as_link(self):
        '''Init a link from string form'''
        fstr = '0 120755 %s %s %s 7 link>>> target_file' % \
            (self.user, self.group, time.time())
        fh = FileHash.init_from_string(fstr, root='/')
        self.assertFalse(fh.is_file)
        self.assertFalse(fh.is_dir)
        self.assertTrue(fh.is_link)
        self.assertEquals(fh.link_target, 'target_file')
        self.assertEquals(fh.fpath, 'link')

    def test_create_as_device_fails(self):
        '''Init a device from string form fails'''
        with self.assertRaises(UnsupportedFileTypeException):
            fstr = '0 020666 %s %s %s 0 /dev/zero' % \
                (self.user, self.group, time.time())
            FileHash.init_from_string(fstr, root='/')

    def test_create_as_socket_fails(self):
        '''Init a socket from string form fails'''
        with self.assertRaises(UnsupportedFileTypeException):
            fstr = '0 140666 %s %s %s 0 /var/run/something.sock' % \
                (self.user, self.group, time.time())
            FileHash.init_from_string(fstr, root='/')

    def test_create_as_file_with_space(self):
        fstr = '0 100644 %s %s %s 100 /etc/hosts in space' % \
            (self.user, self.group, time.time())
        fh = FileHash.init_from_string(fstr, root='/etc')
        self.assertTrue(fh.is_file)
        self.assertFalse(fh.is_dir)
        self.assertFalse(fh.is_link)
        self.assertTrue(fh.size, 100)
        self.assertEquals(fh.fpath, '/etc/hosts in space')


class FileHashCompareUnitTestCase(unittest.TestCase):

    '''Test the file comparison functions'''

    me = inspect.getfile(inspect.currentframe())
    topdir = os.path.join(os.path.dirname(me), 'test')

    mapper = UidGidMapper()

    @classmethod
    def setUpClass(self):
        self.user = self.mapper.get_name_for_uid(os.getuid())
        self.group = self.mapper.get_group_for_gid(os.getgid())

    def tearDown(self):
        if hasattr(self, 'tmp') and self.tmp:
            shutil.rmtree(self.tmp, True)

    def test_safe_to_skip(self):
        '''Test safe_to_skip()'''
        fstr = '0 100644 %s %s %s 100 /etc/hosts' % \
            (self.user, self.group, time.time())
        fh = FileHash.init_from_string(fstr, root='/etc')

        # Same everything.
        fh_same = FileHash.init_from_string(fstr, root='/etc')
        self.assertTrue(fh.safe_to_skip(fh_same))

        # Different name (duh).
        fstr_name = '0 100644 %s %s %s 100 /etc/hosts1' % \
            (self.user, self.group, time.time())
        fh_name = FileHash.init_from_string(fstr_name, root='/etc')
        self.assertFalse(fh.safe_to_skip(fh_name))

        # Different size.
        fstr_size = '0 100644 %s %s %s 101 /etc/hosts1' % \
            (self.user, self.group, time.time())
        fh_size = FileHash.init_from_string(fstr_size, root='/etc')
        self.assertFalse(fh.safe_to_skip(fh_size))

        # Different mtime.
        fstr_mtime = '0 100644 %s %s %s 101 /etc/hosts1' % \
            (self.user, self.group, time.time() + 1)
        fh_mtime = FileHash.init_from_string(fstr_mtime, root='/etc')
        self.assertFalse(fh.safe_to_skip(fh_mtime))

    def test_compare(self):
        '''Test compare()'''

        fstr = '0 100644 %s %s %s 100 /etc/hosts' % \
            (self.user, self.group, time.time())
        fh = FileHash.init_from_string(fstr, root='/etc')

        # Same everything.
        fh_other = FileHash.init_from_string(fstr, root='/etc')
        self.assertTrue(fh.compare(fh_other))
        self.assertTrue(fh.compare(fh_other, trust_mtime=False))
        self.assertTrue(fh.compare(fh_other, ignore_uid_gid=True))
        self.assertTrue(fh.compare(fh_other, ignore_mode=True))

        # Different name (duh).
        fstr_other = '0 100644 %s %s %s 100 /etc/hosts1' % \
            (self.user, self.group, time.time())
        fh_other = FileHash.init_from_string(fstr_other, root='/etc')
        self.assertFalse(fh.compare(fh_other))
        self.assertFalse(fh.compare(fh_other, trust_mtime=False))
        self.assertFalse(fh.compare(fh_other, ignore_uid_gid=True))
        self.assertFalse(fh.compare(fh_other, ignore_mode=True))

        # Different size.
        fstr_size = '0 100644 %s %s %s 101 /etc/hosts1' % \
            (self.user, self.group, time.time())
        fh_other = FileHash.init_from_string(fstr_size, root='/etc')
        self.assertFalse(fh.compare(fh_other))
        self.assertFalse(fh.compare(fh_other, trust_mtime=False))
        self.assertFalse(fh.compare(fh_other, ignore_uid_gid=True))
        self.assertFalse(fh.compare(fh_other, ignore_mode=True))

        # Different mtime.
        fstr_mtime = '0 100644 %s %s %s 101 /etc/hosts1' % \
            (self.user, self.group, time.time() + 1)
        fh_other = FileHash.init_from_string(fstr_mtime, root='/etc')
        self.assertFalse(fh.compare(fh_other))
        self.assertFalse(fh.compare(fh_other, trust_mtime=False))
        self.assertFalse(fh.compare(fh_other, ignore_uid_gid=True))
        self.assertFalse(fh.compare(fh_other, ignore_mode=True))


class FileHashSymlinkSourceNormUnitTestcase(unittest.TestCase):

    me = inspect.getfile(inspect.currentframe())
    topdir = os.path.join(os.path.dirname(me), 'test')

    # Three directories deep. '../../../target' is ok. '../../../../target'
    # is not ok.
    tdir = 'source/d1/d1.1'

    mapper = UidGidMapper()

    @classmethod
    def setUpClass(self):
        self.user = self.mapper.get_name_for_uid(os.getuid())
        self.group = self.mapper.get_group_for_gid(os.getgid())
        self.linkbase = "0 120644 %s %s 0 0 " % (self.user, self.group)

    def tearDown(self):
        if self.tmp:
            shutil.rmtree(self.tmp, True)

    def _symlink_norm(self, link, tgt, absfail=False, check=True):

        tmp = os.path.join(self.topdir, "tmp")
        self.tmp = tmp

        (ldir, lfile) = os.path.split(link)
        log.debug("ldir %s lfile %s", ldir, lfile)

        shutil.rmtree(tmp, True)
        os.makedirs(tmp)

        if ldir:
            self.ldir_real = os.path.join(tmp, ldir)
            log.debug("ldir_real %s", self.ldir_real)
            os.makedirs(self.ldir_real)

        os.symlink(tgt, os.path.join(self.tmp, link))

        linkstr = self.linkbase + '%s/%s>>> %s' % (ldir, lfile, tgt)
        fh = FileHash.init_from_string(linkstr, trim=True, root=self.tmp)

        self.assertIsInstance(fh, FileHash, "Can create link FileHash")
        norm_tpath = fh.source_symlink_make_relative(self.tmp,
                                                     absolute_is_error=absfail)
        if check:
            self.assertEqual(norm_tpath, tgt)
        return (fh, norm_tpath)

    def test_symlink_relative_up(self):
        '''In-tree symlinks relative simple'''
        link = os.path.join(self.tdir, 'link')
        for tgt in ('target', '../target', '../../target',
                    '../../../target'):

            (fh, np) = self._symlink_norm(link, tgt, absfail=True)
            self.assertFalse(fh.link_is_external, "External flag not set")
            self.assertEqual(tgt, fh.link_target, "Object link target set")

    def test_symlink_norm_up_l4_throw(self):
        '''Link points up one directory too many, don't allow'''
        with self.assertRaises(SymlinkPointsOutsideTreeError):
            self._symlink_norm('link', '../../../../target', absfail=True)

    def test_symlink_norm_up_l4_abs(self):
        '''Link points up one directory too many, abs link results'''
        link = os.path.join(self.tdir, 'link')
        (fh, norm_tpath) = self._symlink_norm(link, '../../../../target',
                                              check=False)
        # It will point to topdir, not self.tmp which is a subdir of topdir.
        # That's the point.
        self.assertEqual(norm_tpath, os.path.join(self.topdir, 'target'),
                         "Absolute link is correct")
        self.assertTrue(fh.link_is_external, "External flag is set properly")
        fh.normalise_symlink(self.topdir)
        self.assertEqual(fh.link_target, os.path.join(self.topdir, 'target'),
                         "Object link is correct")

    def test_symlink_norm_inside(self):
        '''In-tree symlinks relative 2'''
        for tgt in ('source/d1/d1.2/target', 'source/d1/target',
                    'source/target', 'target'):
            (fh, np) = self._symlink_norm('source/link', tgt, absfail=True)
            self.assertEqual(np, tgt, "Link stays inbound")
            self.assertEqual(tgt, fh.link_target, "Object link target set")

class FileHashObjectHashableUnitTestcase(unittest.TestCase):

    me = inspect.getfile(inspect.currentframe())
    topdir = os.path.join(os.path.dirname(me), 'test')

    mapper = UidGidMapper()

    @classmethod
    def setUpClass(self):
        self.user = self.mapper.get_name_for_uid(os.getuid())
        self.group = self.mapper.get_group_for_gid(os.getgid())

    def tearDown(self):
        if hasattr(self, 'tmp') and self.tmp:
            shutil.rmtree(self.tmp, True)

    def test_equals_string(self):
        '''Obvious string filehash tests'''
        fha = FileHash.init_from_string("0 100644 %s %s 0 0 test" %
                                        (self.user, self.group))

        fh = FileHash.init_from_string("0 100644 %s %s 0 0 test" %
                                       (self.user, self.group))
        self.assertEqual(fha, fh, "Ident initialiser => eq")

        fh = FileHash.init_from_string("1 100644 %s %s 0 0 test" %
                                       (self.user, self.group))
        self.assertNotEqual(fha, fh, "Hash change => neq")

        fh = FileHash.init_from_string("0 100664 %s %s 0 0 test" %
                                       (self.user, self.group))
        self.assertNotEqual(fha, fh, "Mode change => neq")

        fh = FileHash.init_from_string("0 100644 %s %s 0 0 test" %
                                       ('user2', self.group))
        self.assertNotEqual(fha, fh, "User change => neq")

        fh = FileHash.init_from_string("0 100644 %s %s 0 0 test" %
                                       (self.user, 'group2'))
        self.assertNotEqual(fha, fh, "Group change => neq")

        fh = FileHash.init_from_string("0 100644 %s %s 1 0 test" %
                                       (self.user, self.group))
        self.assertNotEqual(fha, fh, "Mtime change => neq")

        fh = FileHash.init_from_string("0 100644 %s %s 0 1 test" %
                                       (self.user, self.group))
        self.assertNotEqual(fha, fh, "Size change => neq")

        fh = FileHash.init_from_string("0 100644 %s %s 0 0 test2" %
                                       (self.user, self.group))
        self.assertNotEqual(fha, fh, "Filename change => neq")

    def test_equals_file(self):
        tname = os.path.join(self.topdir, 'testfile')
        with open(tname, "wb") as f:
            f.write("Rhubarb")
        fha = FileHash.init_from_file(tname)
        orig_st = os.stat(tname) # We'll use this later.

        fh = FileHash.init_from_file(tname)
        self.assertEqual(fha, fh, "Exact same file => eq")

        tname_1 = tname + '1'
        with open(tname_1, "wb") as f:
            f.write("Rhubarb")
        fh = FileHash.init_from_file(tname_1)
        self.assertNotEqual(fha, fh, "Different name, time => neq")

        # Write the same file again, which will change the time.
        with open(tname, "wb") as f:
            f.write("Rhubarb")
        fh = FileHash.init_from_file(tname)
        self.assertNotEqual(fha, fh, "Different mtime => neq")

        # Now reset the mtime and compare.
        os.utime(tname, (orig_st.st_atime, orig_st.st_mtime))
        fh = FileHash.init_from_file(tname)
        self.assertEqual(fha, fh, "New file, same contents, same mtime => eq")


class FileHashObjectPicklableUnitTestcase(unittest.TestCase):

    me = inspect.getfile(inspect.currentframe())
    topdir = os.path.join(os.path.dirname(me), 'test')

    mapper = UidGidMapper()

    @classmethod
    def setUpClass(self):
        self.user = self.mapper.get_name_for_uid(os.getuid())
        self.group = self.mapper.get_group_for_gid(os.getgid())

    def tearDown(self):
        if hasattr(self, 'tmp') and self.tmp:
            shutil.rmtree(self.tmp, True)

    def test_pickle(self):
        tname = os.path.join(self.topdir, 'testfile_pickle')
        with open(tname, "wb") as f:
            f.write("Rhubarb")
        fha = FileHash.init_from_file(tname)
        p = pickle.dumps(fha)
        self.assertIsNotNone(p, "Pickle of FileHash is not None")
        self.assertNotEqual(p, "", "Pickle of FileHash is not empty string")

        fh = FileHash.init_from_file(tname) # Same object.
        p2 = pickle.dumps(fha)
        self.assertEqual(p, p2, "Pickles of same filehash are the same")
