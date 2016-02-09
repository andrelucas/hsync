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
import unittest

from hsync.exceptions import *
from hsync.filehash import *
from hsync.hashlist import *
from hsync.idmapper import *


class HashListTestCase(unittest.TestCase):

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

    def test_init(self):
        '''Object creation tests'''
        hl = HashList()
        self.assertIsNotNone(hl, "Non-null object returned")

    def test_append(self):
        '''Object can be appended'''
        hl = HashList()

        fh = FileHash.init_from_string("0 100644 %s %s 0 0 test" %
                                       (self.user, self.group))

        # This should not raise.
        hl.append(fh)

        # Attempting to append a non-FileHash should raise.
        with self.assertRaises(NotAFileHashError):
            hl.append(None)
        with self.assertRaises(NotAFileHashError):
            hl.append("Nope")

    def test_duplicate_raise(self):
        '''Check exceptions are properly raised'''
        hl = HashList(raise_on_duplicates=True)

        fh = FileHash.init_from_string("0 100644 %s %s 0 0 test" %
                                       (self.user, self.group))

        # This should not raise.
        hl.append(fh)
        self.assertEqual(len(hl), 1)
        # Duplicate should raise.
        with self.assertRaises(DuplicateEntryInHashListError):
            hl.append(fh)

        '''Check exceptions are properly raised'''
        hl = HashList(raise_on_duplicates=False)

        fh = FileHash.init_from_string("0 100644 %s %s 0 0 test" %
                                       (self.user, self.group))

        # This should not raise.
        hl.append(fh)
        # Duplicate should not raise.
        hl.append(fh)
        self.assertEqual(len(hl), 2)

    def test_list_iterator(self):
        '''Check we can iterate over the list properly'''
        hl = HashList()

        fhlist = []
        pfx = "0 100644 %s %s 0 0 test" % (self.user, self.group)

        for n in xrange(100):
            fh = FileHash.init_from_string(pfx + '%0.2i' % n)
            fhlist.append(fh)

        hl.extend(fhlist)
        self.assertEqual(len(hl), len(fhlist))

        for n, fh in enumerate(hl):
            self.assertEqual(fh, fhlist[n])

    def test_list_indexing(self):
        '''Check we can iterate over the list properly'''
        hl = HashList()

        fhlist = []
        pfx = "0 100644 %s %s 0 0 test" % (self.user, self.group)

        for n in xrange(100):
            fh = FileHash.init_from_string(pfx + '%0.2i' % n)
            fhlist.append(fh)

        hl.extend(fhlist)
        self.assertEqual(len(hl), len(fhlist))

        for n in xrange(100):
            self.assertEqual(hl[n], fhlist[n])
