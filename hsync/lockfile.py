# Simple lockfile.

from __future__ import print_function

import logging
import os
from subprocess import Popen, PIPE
import sys

from exceptions import *


log = logging.getLogger()


class LockFile(object):

    def __init__(self, lockfilename, break_dead_lockfile=True):

        self.lockfilename = lockfilename
        self.lock = None
        lockdir = os.path.dirname(lockfilename)
        if not os.path.isdir(lockdir):
            raise NotADirectoryError("Attempting to create lockfile %s "
                                     "in non-directory" % lockfilename)

        if break_dead_lockfile:
            self._break_attempt()

        log.debug("Attempting to open lockfile %s", lockfilename)
        try:
            lock = os.open(
                lockfilename, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
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

    def _break_attempt(self):
        try:
            lock = open(self.lockfilename)
        except IOError:
            log.debug("No pre-existing lockfile '%s' seen", self.lockfilename)
            return

        lines = lock.readlines()
        if len(lines) != 2:
            # That's serious - it should be the right format, at least.
            raise Exception("Lock file '%s' malformed" %
                            self.lockfilename)
        (lpid, _argv0) = lines
        try:
            lpid = int(lpid)
        except ValueError:
            raise Exception("Lock file '%s' malformed PID '%s'" %
                            (self.lockfilename, lpid))

        # See if there's a process with the matching pid with an
        # executable that's the same as ours.
        cmd = ('ps -o command= -p %s' % lpid).split()

        log.debug("Running '%s' to check for existing process", cmd)
        p = Popen(cmd, shell=False, stdout=PIPE, close_fds=True)
        (output, _err) = p.communicate()
        log.debug("'%s' cmd output: %s", cmd, output.splitlines())

        if not output:
            log.debug("Failed to find process %i", lpid)
            log.info("Removing dead lockfile '%s'", self.lockfilename)
            os.unlink(self.lockfilename)

        lock.close()
        return

    def __del__(self):
        log.debug("LockFile __del__()")
        self.remove()


class LockFileManager(object):

    def __init__(self, lockfilename, break_dead_lockfile=True):
        self.lockfilename = lockfilename
        self.break_dead_lockfile = break_dead_lockfile

    def __enter__(self):
        self.lock = LockFile(self.lockfilename, self.break_dead_lockfile)
        return self.lock

    def __exit__(self, exc_type, exc_value, exc_tb):
        # Don't care about the exception.
        self.lock.remove()
        self.lock = None
