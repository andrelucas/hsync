
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

#
# Number formatting for progress meters.
#

import logging

log = logging.getLogger()


SingleByte = 1

# IEC units.
KiB = 1024
MiB = 1024 * KiB
GiB = 1024 * MiB
TiB = 1024 * GiB

# SI units.
kB = 1000
MB = 1000 * kB
GB = 1000 * MB
TB = 1000 * GB

threshold = 0.9


class SizeAction(object):

    def __init__(self, upperbound, divisor, unit, format):
        self.upperbound = upperbound
        self.divisor = divisor
        self.unit = unit
        self.format = format


class ByteUnitConverter(object):

    @classmethod
    def select_sact(cls, bytes):
        for sact in cls.action:
            if sact.upperbound is None:
                return sact
            elif bytes < threshold * sact.upperbound:
                return sact

    @classmethod
    def bytes_to_unit(cls, bytes):
        sact = cls.select_sact(bytes)
        fmt = sact.format
        return fmt % (1.0 * bytes / sact.divisor) + sact.unit

    @classmethod
    def unit_for_bytes(cls, bytes):
        sact = cls.select_sact(bytes)
        return sact.unit


class IECUnitConverter(ByteUnitConverter):

    action = [
        SizeAction(KiB, 1, 'B', '%6.0f'),
        SizeAction(MiB, KiB, 'KiB', '%6.1f'),
        SizeAction(GiB, MiB, 'MiB', '%6.2f'),
        SizeAction(TiB, GiB, 'GiB', '%6.3f'),
        SizeAction(None, TiB, 'TiB', '%6.4f'),
    ]


class SIUnitConverter(ByteUnitConverter):

    action = [
        SizeAction(kB, 1, 'B', '%6.0f'),
        SizeAction(MB, kB, 'kB', '%6.1f'),
        SizeAction(GB, MB, 'MB', '%6.2f'),
        SizeAction(TB, GB, 'GB', '%6.3f'),
        SizeAction(None, TB, 'TB', '%6.4f'),
    ]
