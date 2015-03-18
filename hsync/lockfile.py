# Simple lockfile.

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
