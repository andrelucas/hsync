# Unit test for stats collector object.

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

import unittest

from hsync.stats import *


class StatsCollectorUnitTestCase(unittest.TestCase):

    def test_basic1(self):
        '''Simple set test'''
        s = StatsCollector.init('statstest', ['a', 'b'])
        s.a += 1
        s.b = 2
        self.assertEquals(s.a, 1, "Increment")
        self.assertEquals(s.b, 2, "Set directly")

    def test_unknown_attr_fail(self):
        '''Unknown attribute should raise'''
        s = StatsCollector.init('statstest', ['a', 'b'])
        with self.assertRaises(TypeError):
            s.c = 1

    def test_add_del_attr(self):
        '''Can add and delete attributes'''
        s = StatsCollector.init('statstest', ['a', 'b'])
        with self.assertRaises(TypeError):
            s.c = 3
        s.add_attributes(['c'])
        s.c = 3
        self.assertEquals(s.c, 3, "Set new attr")
        s.del_attributes(['b'])
        with self.assertRaises(TypeError):
            s.b = 2

    def test_iteritems(self):
        '''iteritems() works'''
        s = StatsCollector.init('statstest', ['a', 'b', 'c'])
        s.a = 1
        s.b = 2
        s.c = 3
        copy = {}
        for k, v in s.iteritems():
            copy[k] = v

        test = {'a': 1, 'b': 2, 'c': 3}
        self.assertEquals(copy, test)

    def test_check_str(self):
        '''str() works'''
        s = StatsCollector.init('statstest', ['a', 'b'])
        s.a = 1
        s.b = 2
        self.assertEquals(str(s), 'statstest: a=1, b=2',
                          "str() is as expected")
