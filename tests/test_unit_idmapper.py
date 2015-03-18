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
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import grp
import logging
import os
import pwd
import unittest

from hsync.idmapper import *
from hsync.utility import is_dir_excluded, is_path_pre_excluded

log = logging.getLogger()


class FileHashSymlinkSourceNormUnitTestcase(unittest.TestCase):

    my_uid = os.getuid()
    my_gid = os.getgid()
    my_name = pwd.getpwuid(my_uid).pw_name
    my_group = grp.getgrgid(my_gid).gr_name

    def setUp(self):
        self.m = UidGidMapper()

    def test_obvious(self):
        '''Test obvious uid and gid idmapper mappings'''
        self.assertEquals(self.m.get_name_for_uid(os.getuid()), self.my_name,
                          "uid->name is mapped properly")
        self.assertEquals(self.m.get_uid_for_name(self.my_name), self.my_uid,
                          "name->uid is mapped properly")
        self.assertEquals(self.m.get_group_for_gid(os.getgid()), self.my_group,
                          "gid->group is mapped properly")
        self.assertEquals(self.m.get_gid_for_group(self.my_group), self.my_gid,
                          "group->gid is mapped properly")

    def test_nonExistentIds(self):
        '''Bogus idmapper uid and gid should not cause KeyError'''
        self.assertEquals(self.m.get_name_for_uid(99999), self.my_name,
                          "Bogus uid should not throw KeyError")
        self.assertEquals(self.m.get_group_for_gid(99999), self.my_group,
                          "Bogus gid should not throw KeyError")

    def test_nonExistentNames(self):
        '''Bogus idmapper user and group should not cause KeyError'''
        self.assertEquals(self.m.get_uid_for_name('bogusname'),
                          self.my_uid, "Bogus name should not throw KeyError")
        self.assertEquals(self.m.get_gid_for_group('bogusgroup'),
                          self.my_gid, "Bogus group should not throw KeyError")

    def test_good_defaults(self):
        '''Sensible defaults are accepted and get obvious results'''
        self.m.set_default_uid(self.my_uid)
        self.assertEquals(self.m.default_name, self.my_name)
        self.m.set_default_name(self.my_name)
        self.assertEquals(self.m.default_uid, self.my_uid)
        self.m.set_default_gid(self.my_gid)
        self.assertEquals(self.m.default_group, self.my_group)
        self.m.set_default_group(self.my_group)
        self.assertEquals(self.m.default_gid, self.my_gid)

    def test_bad_defaults_raise(self):
        '''Bogus idmapper set_default_*()s raise exceptions'''
        with self.assertRaises(KeyError):
            self.m.set_default_uid(99999)

        with self.assertRaises(KeyError):
            self.m.set_default_gid(99999)

        with self.assertRaises(KeyError):
            self.m.set_default_name('madeupname')

        with self.assertRaises(KeyError):
            self.m.set_default_group('madeupgroup')
