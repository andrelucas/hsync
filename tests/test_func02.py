# Functional tests for hsync

from __future__ import print_function

import collections
import inspect
import logging
import os
import shutil
import subprocess
import unittest

from hsync._version import __version__

log = logging.getLogger()


class HsyncLocalDiskFuncTestCase(unittest.TestCase):

    me = inspect.getfile(inspect.currentframe())
    medir = os.path.dirname(me)
    topdir = os.path.join(medir, 'test')
    in_tmp = os.path.join(topdir, 'in_tmp')
    out_tmp = os.path.join(topdir, 'out_tmp')
    hsync_bin = "hsync/hsync.py"

    def tearDown(self):
        shutil.rmtree(self.in_tmp, True)
        shutil.rmtree(self.out_tmp, True)

    def _just_remove(self, path):
        if os.path.exists(path):
            if os.path.isdir(path):
                shutil.rmtree(path, True)
            else:
                os.unlink(path)

    def _run_hsync(self, opts):
        if isinstance(opts, str):
            opts = opts.split()

        cmdopt = ['/usr/bin/env', 'python', self.hsync_bin]
        cmdopt.extend(opts)
        subprocess.check_call(cmdopt)

    def _grab_hsync(self, opts):
        if isinstance(opts, str):
            opts = opts.split()

        cmdopt = ['/usr/bin/env', 'python', self.hsync_bin]
        cmdopt.extend(opts)
        subprocess.check_call(cmdopt)

    def test_runtest(self):
        self._grab_hsync('--version')


