# Simple lockfile.

from __future__ import print_function

import logging
import os
import sys

from exceptions import *


log = logging.getLogger()


class LockFile(object):

	def __init__(self, lockfilename):

		self.lockfilename = lockfilename
		self.lock = None
		lockdir = os.path.dirname(lockfilename)
		if not os.path.isdir(lockdir):
			raise NotADirectoryError("Attempting to create lockfile %s "
										"in non-directory" % lockfilename)
		log.debug("Attempting to open lockfile %s", lockfilename)
		try:
			lock = os.open(lockfilename, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
			self.lock = os.fdopen(lock, 'w')

		except OSError as e:
			log.debug("Lockfile open failed: %s", e)
			i = sys.exc_info()
			raise i[0], i[1], i[2]

		print('%s\n%s' % (os.getpid(), sys.argv[0]), file=self.lock)
		self.lock.flush()
		log.debug("Lock open")


	def remove(self):
		log.debug("LockFile remove()")
		if hasattr(self, 'lock') and self.lock is not None:
			log.debug("Removing lockfile")
			self.lock.close()
			self.lock = None
			if os.path.isfile(self.lockfilename):
				os.unlink(self.lockfilename)
			self.lockfilename = None


	def __del__(self):
		log.debug("LockFile __del__()")
		self.remove()


class LockFileManager(object):

	def __init__(self, lockfilename):
		self.lockfilename = lockfilename


	def __enter__(self):
		self.lock = LockFile(self.lockfilename)
		return self.lock


	def __exit__(self, exc_type, exc_value, exc_tb):
		# Don't care about the exception.
		self.lock.remove()
		self.lock = None

