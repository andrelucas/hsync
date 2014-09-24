#
# Number formatting for progress meters.
#

import logging
from math import floor
import unittest


log = logging.getLogger()


# IEC units.
KiB = 1024
MiB = 1024 * KiB
GiB = 1024 * MiB

# SI units.
kB = 1000
MB = 1000 * kB
GB = 1000 * MB

threshold = 0.9

def bytes_to_iec(bytes):
	
	if bytes < threshold*KiB:
		return '%dB' % (bytes)

	elif bytes < threshold*MiB:
		return '%6.1fKiB' % (1.0*bytes/KiB)

	elif bytes < threshold * GiB:
		return '%6.2fMiB' % (1.0*bytes/MiB)

	else:
		return '%6.3fGiB' % (1.0*bytes/GiB)


def bytes_to_si(bytes):
	if bytes < threshold*kB:
		return '%dB' % (bytes)

	elif bytes < threshold*MB:
		return '%6.1fkB' % (1.0*bytes/kB)

	elif bytes < threshold * GB:
		return '%6.2fMB' % (1.0*bytes/MB)

	else:
		return '%6.3fGB' % (1.0*bytes/GB)



