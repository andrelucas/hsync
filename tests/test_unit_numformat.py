
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

from math import floor
import unittest

from hsync.numformat import *


class NumFormatTestCase(unittest.TestCase):

    def test_iec_simple(self):
        '''Whole-number IEC units are exactly correct'''
        self.assertEquals(
            IECUnitConverter.bytes_to_unit(1024).lstrip(),
            '1.0KiB')
        self.assertEquals(
            IECUnitConverter.bytes_to_unit(1024 * 1024).lstrip(),
            '1.00MiB')
        self.assertEquals(
            IECUnitConverter.bytes_to_unit(1024 ** 3).lstrip(),
            '1.000GiB')
        self.assertEquals(
            IECUnitConverter.bytes_to_unit(1024 ** 4).lstrip(),
            '1.0000TiB')

    def test_iec_overlimit(self):
        '''Exceeding the largest IEC unit is ok'''
        self.assertEquals(
            IECUnitConverter.bytes_to_unit(1024 ** 5).lstrip(),
            '1024.0000TiB')

    def test_unit_fetch(self):
        '''Can look up the unit for various byte values'''
        self.assertEquals(IECUnitConverter.unit_for_bytes(1024 ** 0), 'B')
        self.assertEquals(SIUnitConverter.unit_for_bytes(1000 ** 0), 'B')
        self.assertEquals(IECUnitConverter.unit_for_bytes(1024 ** 1), 'KiB')
        self.assertEquals(SIUnitConverter.unit_for_bytes(1000 ** 1), 'kB')

    def test_si_simple(self):
        '''Whole-number SI units are exactly correct'''
        self.assertEquals(
            SIUnitConverter.bytes_to_unit(1000).lstrip(),
            '1.0kB')
        self.assertEquals(
            SIUnitConverter.bytes_to_unit(1000 * 1000).lstrip(),
            '1.00MB')
        self.assertEquals(
            SIUnitConverter.bytes_to_unit(1000 ** 3).lstrip(),
            '1.000GB')
        self.assertEquals(
            SIUnitConverter.bytes_to_unit(1000 ** 4).lstrip(),
            '1.0000TB')

    def test_si_overlimit(self):
        '''Exceeding the largest IEC unit is ok'''
        self.assertEquals(
            SIUnitConverter.bytes_to_unit(1000 ** 5).lstrip(),
            '1000.0000TB')

    def test_iec_thresh(self):
        '''Test edge cases for IEC'''
        bytes_edge = floor(threshold * KiB)
        self.assertEquals(
            IECUnitConverter.bytes_to_unit(bytes_edge).lstrip(), '921B')
        self.assertEquals(
            IECUnitConverter.bytes_to_unit(bytes_edge + 1).lstrip(), '0.9KiB')

        megabytes_edge = floor(threshold * MiB)
        self.assertTrue(
            IECUnitConverter.bytes_to_unit(megabytes_edge).endswith('KiB'))
        self.assertTrue(
            IECUnitConverter.bytes_to_unit(megabytes_edge + 1).endswith('MiB'))

        gigabytes_edge = floor(threshold * GiB)
        self.assertTrue(
            IECUnitConverter.bytes_to_unit(gigabytes_edge).endswith('MiB'))
        self.assertTrue(
            IECUnitConverter.bytes_to_unit(gigabytes_edge + 1).endswith('GiB'))

    def test_si_thresh(self):
        '''Test edge cases for IEC'''
        bytes_edge = floor(threshold * kB) - 1
        self.assertEquals(
            SIUnitConverter.bytes_to_unit(bytes_edge).lstrip(), '899B')
        self.assertEquals(
            SIUnitConverter.bytes_to_unit(bytes_edge + 1).lstrip(), '0.9kB')

        megabytes_edge = floor(threshold * MB) - 1
        self.assertTrue(
            SIUnitConverter.bytes_to_unit(megabytes_edge).endswith('kB'))
        self.assertTrue(
            SIUnitConverter.bytes_to_unit(megabytes_edge + 1).endswith('MB'))

        gigabytes_edge = floor(threshold * GB) - 1
        self.assertTrue(
            SIUnitConverter.bytes_to_unit(gigabytes_edge).endswith('MB'))
        self.assertTrue(
            SIUnitConverter.bytes_to_unit(gigabytes_edge + 1).endswith('GB'))
