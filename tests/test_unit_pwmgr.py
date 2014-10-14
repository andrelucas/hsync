# Test (trivially) the local password manager wrapper.

from __future__ import print_function

import logging
import unittest

from hsync.local_pwmgr import InstrumentedHTTPPassManager

log = logging.getLogger()


class TestUnitLocalPwmgr(unittest.TestCase):

    def test_exercise(self):
        '''Set and get a password'''
        pwmgr = InstrumentedHTTPPassManager()
        pwmgr.add_password('some_realm', '127.0.0.1', 'user', 'password')
        (user, pw) = pwmgr.find_user_password('some_realm', '127.0.0.1')
        self.assertEquals((user, pw), ('user', 'password'))

    def test_default_realm(self):
        '''Set and get a password with a default realm'''
        pwmgr = InstrumentedHTTPPassManager()
        pwmgr.add_password(None, '127.0.0.1', 'user', 'password')
        (user, pw) = pwmgr.find_user_password('some_realm', '127.0.0.1')
        self.assertEquals((user, pw), ('user', 'password'))
