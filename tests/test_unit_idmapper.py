#!/usr/bin/env python

import grp
import logging
import os
import pwd
import unittest

from hsync.idmapper import *

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
