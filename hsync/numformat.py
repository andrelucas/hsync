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
