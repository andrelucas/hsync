# Functional tests for hsync
#
# Call out to the script, no running main() directly.

from __future__ import print_function

import inspect
import logging
import os
import shutil
from subprocess import *
import unittest

from hsync._version import __version__

log = logging.getLogger()


class HsyncLocalDiskFuncTestCase(unittest.TestCase):

    me = inspect.getfile(inspect.currentframe())
    medir = os.path.dirname(me)
    rundir = os.path.realpath(os.path.join(medir, '..'))
    topdir = os.path.join(medir, 'test')
    in_tmp = os.path.join(topdir, 'in_tmp')
    out_tmp = os.path.join(topdir, 'out_tmp')
    hsync_bin = "hsync/hsync.py"
    zlib_tarball = os.path.join(topdir, 'zlib-1.2.8.tar.gz')
    zlib_extracted = os.path.join(topdir, 'zlib-1.2.8')

    def setUp(self):
        os.chdir(self.rundir)
        for d in self.in_tmp, self.out_tmp:
            self._just_remove(d)
            os.makedirs(d)

    def tearDown(self):
        for d in self.in_tmp, self.out_tmp, self.zlib_extracted:
            self._just_remove(d)

    def _just_remove(self, path):
        if os.path.exists(path):
            if os.path.isdir(path):
                shutil.rmtree(path, True)
            else:
                os.unlink(path)

    def _prep_run(self, opts):
        if isinstance(opts, str):
            opts = opts.split()

        cmdopt = ['/usr/bin/env', 'python', self.hsync_bin]
        cmdopt.extend(opts)
        return cmdopt

    def _run_hsync(self, opts):
        cmdopt = self._prep_run(opts)
        check_call(cmdopt)

    def _grab_hsync(self, opts):
        cmdopt = self._prep_run(opts)
        log.debug("_grab_hsync(%s)", cmdopt)
        p = Popen(cmdopt, stdout=PIPE, stderr=PIPE, shell=False)
        (out, err) = p.communicate()
        self.assertIsNotNone(p.returncode)
        return (p.returncode, out, err)

    def _check_grab_hsync(self, opts):
        (ret, out, err) = self._grab_hsync(opts)
        self.assertEquals(ret, 0)
        return (out, err)

    def _dump_err(self, err):
        if log.isEnabledFor(logging.DEBUG):
            log.debug(err)

    def _unpack_tarball(self, dir, tarball):
        check_call('cd %s; tar xzf %s' % (dir, tarball),
                   shell=True)

    def test_run_version(self):
        '''Get the expected version number'''
        (verstr, err) = self._check_grab_hsync('--version')
        self.assertEquals(verstr, 'Hsync version %s\n' % __version__)

    def __get_debug(self, err, keyword):
        fhlist = []
        in_dbg = False
        done_dbg = False

        for line in err.splitlines():
            if done_dbg:
                continue

            if not in_dbg:
                if line.startswith("XDEBUG BEGIN %s" % keyword):
                    in_dbg = True
            else:
                if line.startswith("XDEBUG END %s" % keyword):
                    in_dbg = False
                    done_dbg = True
                else:
                    fhlist.append(line.split(','))

        if not done_dbg:
            raise Exception("No complete 'XDEBUG END %s' section found"
                            % keyword)

        return fhlist

    def _get_scan_debug(self, err):
        return self.__get_debug(err, 'scan')

    def _get_check_debug(self, err):
        return (self.__get_debug(err, "check needed"),
                self.__get_debug(err, "check not_needed"))

    def _path_in_list(self, path, flist, dir=True):
        # Assert that a path is found in the given filelist.
        if dir:
            if not path.endswith(os.sep):
                path += os.sep

        for fpath in flist:
            if fpath.startswith(path):
                log.debug("_path_in_list: '%s' matches '%s'", fpath, path)
                return True

        return False

    def test_e2e_simple1(self):
        '''Run a simple end-to-end'''
        self._unpack_tarball(self.in_tmp, self.zlib_tarball)
        zlibsrc = os.path.join(self.in_tmp, 'zlib-1.2.8')
        zlibdst = os.path.join(self.out_tmp, 'zlib-1.2.8')
        (out, err) = self._check_grab_hsync('-S %s -z --scan-debug' % zlibsrc)
        scanlist = self._get_scan_debug(err)

        (out, err) = self._check_grab_hsync('-D %s -u %s -Z --check-debug' %
                                            (zlibdst, zlibsrc))
        (needed, not_needed) = self._get_check_debug(err)

        # Check we fetched the exact files we expected to fetch.
        scanfiles = [f[0] for f in scanlist]
        scanfiles.sort()
        fetchfiles = [f[0] for f in needed]
        fetchfiles.sort()
        self.assertEquals(scanfiles, fetchfiles)

    def test_e2e_exclude_dst1(self):
        '''
        Run a transfer with dest -X, check the directory is excluded.
        '''
        self._unpack_tarball(self.in_tmp, self.zlib_tarball)
        zlibsrc = os.path.join(self.in_tmp, 'zlib-1.2.8')
        zlibdst = os.path.join(self.out_tmp, 'zlib-1.2.8')

        # Run a scan excluding the watcom/ directory.
        (out, err) = self._check_grab_hsync('-S %s -z -X watcom --scan-debug'
                                            % zlibsrc)
        scanlist = self._get_scan_debug(err)

        scanfiles = [f[0] for f in scanlist]
        scanfiles.sort()

        # Now run a full scan.
        (out, err) = self._check_grab_hsync('-S %s -z --scan-debug'
                                            % zlibsrc)
        full_scanlist = self._get_scan_debug(err)

        full_scanfiles = [f[0] for f in full_scanlist]
        full_scanfiles.sort()

        # Run hsync -D to fetch without watcom/.
        (out, err) = self._check_grab_hsync('-D %s -u %s -X watcom -Z '
                                            '--check-debug' %
                                            (zlibdst, zlibsrc))
        (needed, not_needed) = self._get_check_debug(err)

        fetchfiles = [f[0] for f in needed]
        fetchfiles.sort()

        # Fetch should match the first scan (with -X), but not the full scan
        # as watcom/ files should not be transferred.
        self.assertNotEquals(full_scanfiles, fetchfiles)
        self.assertEquals(scanfiles, fetchfiles)

        # In the clean scan, watcom/ should be present.
        self.assertTrue(self._path_in_list('watcom/', full_scanfiles))
        # In the -X scan, watcom/ should be absent.
        self.assertFalse(self._path_in_list('watcom/', scanfiles))

    def test_e2e_exclude_dst2(self):
        '''
        Run a transfer with dest -X subdir, check the directory is excluded.
        '''
        self._unpack_tarball(self.in_tmp, self.zlib_tarball)
        zlibsrc = os.path.join(self.in_tmp, 'zlib-1.2.8')
        zlibdst = os.path.join(self.out_tmp, 'zlib-1.2.8')

        # Run a scan excluding the watcom/ directory.
        (out, err) = self._check_grab_hsync('-S %s -z -X contrib/amd64 '
                                            '--scan-debug'
                                            % zlibsrc)
        scanlist = self._get_scan_debug(err)

        scanfiles = [f[0] for f in scanlist]
        scanfiles.sort()

        # Now run a full scan.
        (out, err) = self._check_grab_hsync('-S %s -z --scan-debug'
                                            % zlibsrc)
        full_scanlist = self._get_scan_debug(err)

        full_scanfiles = [f[0] for f in full_scanlist]
        full_scanfiles.sort()

        # Run hsync -D to fetch without watcom/.
        (out, err) = self._check_grab_hsync('-D %s -u %s -X contrib/amd64 -Z '
                                            '--check-debug' %
                                            (zlibdst, zlibsrc))
        (needed, not_needed) = self._get_check_debug(err)

        fetchfiles = [f[0] for f in needed]
        fetchfiles.sort()

        # Fetch should match the first scan (with -X), but not the full scan
        # as watcom/ files should not be transferred.
        self.assertNotEquals(full_scanfiles, fetchfiles)
        self.assertEquals(scanfiles, fetchfiles)

        # In the clean scan, contrib/amd64 should be present.
        self.assertTrue(self._path_in_list('contrib/amd64', full_scanfiles))
        # In the -X scan, contrib/amd64 should be absent.
        self.assertFalse(self._path_in_list('contrib/amd64', scanfiles))
        # In the fetch, contrib/amd64 should be absent.
        self.assertFalse(self._path_in_list('contrib/amd64', fetchfiles))

    def test_e2e_exclude_src1(self):
        '''Run a transfer with src -X, check the directory is excluded.'''
        self._unpack_tarball(self.in_tmp, self.zlib_tarball)
        zlibsrc = os.path.join(self.in_tmp, 'zlib-1.2.8')
        zlibdst = os.path.join(self.out_tmp, 'zlib-1.2.8')

        # Run a full scan.
        (out, err) = self._check_grab_hsync('-S %s -z --scan-debug'
                                            % zlibsrc)
        full_scanlist = self._get_scan_debug(err)

        full_scanfiles = [f[0] for f in full_scanlist]
        full_scanfiles.sort()

        # Now run a new scan excluding the watcom/ directory.
        (out, err) = self._check_grab_hsync('-S %s -z -X watcom --scan-debug'
                                            % zlibsrc)
        scanlist = self._get_scan_debug(err)

        # Run hsync -D to fetch without watcom/.
        (out, err) = self._check_grab_hsync('-D %s -u %s -Z --check-debug' %
                                            (zlibdst, zlibsrc))
        (needed, not_needed) = self._get_check_debug(err)

        # Check we fetched the exact files we expected to fetch.
        scanfiles = [f[0] for f in scanlist]
        scanfiles.sort()

        fetchfiles = [f[0] for f in needed]
        fetchfiles.sort()

        # Fetch should match the second scan (with -X)
        self.assertNotEquals(full_scanfiles, fetchfiles)
        self.assertEquals(scanfiles, fetchfiles)

        # In the clean scan, watcom/ should be present.
        self.assertTrue(self._path_in_list('watcom/', full_scanfiles))
        # In the -X scan, watcom/ should be absent.
        self.assertFalse(self._path_in_list('watcom/', scanfiles))
        # In the fetch, watcom/ should be absent.
        self.assertFalse(self._path_in_list('watcom/', fetchfiles))

    def test_e2e_exclude_src2(self):
        '''
        Run a transfer with src -X subdir, check the directory is
        excluded.
        '''
        self._unpack_tarball(self.in_tmp, self.zlib_tarball)
        zlibsrc = os.path.join(self.in_tmp, 'zlib-1.2.8')
        zlibdst = os.path.join(self.out_tmp, 'zlib-1.2.8')

        # Run a full scan.
        (out, err) = self._check_grab_hsync('-S %s -z --scan-debug'
                                            % zlibsrc)
        full_scanlist = self._get_scan_debug(err)

        full_scanfiles = [f[0] for f in full_scanlist]
        full_scanfiles.sort()

        # Now run a new scan excluding the contrib/amd64/ directory.
        (out, err) = self._check_grab_hsync('-S %s -z -X contrib/amd64 '
                                            '--scan-debug'
                                            % zlibsrc)
        scanlist = self._get_scan_debug(err)

        # Run hsync -D to fetch without contrib/amd64/.
        (out, err) = self._check_grab_hsync('-D %s -u %s -Z --check-debug' %
                                            (zlibdst, zlibsrc))
        (needed, not_needed) = self._get_check_debug(err)

        # Check we fetched the exact files we expected to fetch.
        scanfiles = [f[0] for f in scanlist]
        scanfiles.sort()

        fetchfiles = [f[0] for f in needed]
        fetchfiles.sort()

        # Fetch should match the second scan (with -X)
        self.assertNotEquals(full_scanfiles, fetchfiles)
        self.assertEquals(scanfiles, fetchfiles)

        # In the clean scan, contrib/amd64 should be present.
        self.assertTrue(self._path_in_list('contrib/amd64', full_scanfiles))
        # In the -X scan, contrib/amd64 should be absent.
        self.assertFalse(self._path_in_list('contrib/amd64', scanfiles))
        # In the fetch, contrib/amd64 should be absent.
        self.assertFalse(self._path_in_list('contrib/amd64', fetchfiles))

    def test_e2e_excludeglob_dst1(self):
        '''
        Run a transfer with dest -X glob, check the directory is excluded.
        '''
        self._unpack_tarball(self.in_tmp, self.zlib_tarball)
        zlibsrc = os.path.join(self.in_tmp, 'zlib-1.2.8')
        zlibdst = os.path.join(self.out_tmp, 'zlib-1.2.8')

        # Run a scan excluding the watcom/ directory.
        (out, err) = self._check_grab_hsync('-S %s -z --scan-debug -X wat* '
                                            % zlibsrc)
        scanlist = self._get_scan_debug(err)

        scanfiles = [f[0] for f in scanlist]
        scanfiles.sort()

        # Now run a full scan.
        (out, err) = self._check_grab_hsync('-S %s -z --scan-debug'
                                            % zlibsrc)
        full_scanlist = self._get_scan_debug(err)

        full_scanfiles = [f[0] for f in full_scanlist]
        full_scanfiles.sort()

        # Run hsync -D to fetch without watcom/.
        (out, err) = self._check_grab_hsync('-D %s -u %s -X wat* -Z '
                                            '--check-debug' %
                                            (zlibdst, zlibsrc))
        (needed, not_needed) = self._get_check_debug(err)

        # Check we fetched the exact files we expected to fetch.
        fetchfiles = [f[0] for f in needed]
        fetchfiles.sort()

        # In the clean scan, watcom/ should be present.
        self.assertTrue(self._path_in_list('watcom/', full_scanfiles))
        # In the -X scan, watcom/ should be absent.
        self.assertFalse(self._path_in_list('watcom/', scanfiles))
        # In the fetch, watcom/ should be absent.
        self.assertFalse(self._path_in_list('watcom/', fetchfiles))

        self.assertNotEquals(full_scanfiles, fetchfiles)
        self.assertEquals(scanfiles, fetchfiles)

    def test_e2e_excludeglob_dst2(self):
        '''
        Run a transfer with dest -X glob in subdir, check the right
        directories are excluded.
        '''
        self._unpack_tarball(self.in_tmp, self.zlib_tarball)
        zlibsrc = os.path.join(self.in_tmp, 'zlib-1.2.8')
        zlibdst = os.path.join(self.out_tmp, 'zlib-1.2.8')

        # Run a scan excluding the contrib/a* directories.
        (out, err) = self._check_grab_hsync('-S %s -z -X contrib/a* '
                                            '--scan-debug'
                                            % zlibsrc)
        scanlist = self._get_scan_debug(err)

        scanfiles = [f[0] for f in scanlist]
        scanfiles.sort()

        # Run a full scan.
        (out, err) = self._check_grab_hsync('-S %s -z --scan-debug'
                                            % zlibsrc)
        full_scanlist = self._get_scan_debug(err)

        full_scanfiles = [f[0] for f in full_scanlist]
        full_scanfiles.sort()

        # Run hsync -D to fetch without contrib/a*/.
        (out, err) = self._check_grab_hsync('-D %s -u %s -Z --check-debug '
                                            '-X contrib/a*' %
                                            (zlibdst, zlibsrc))
        (needed, not_needed) = self._get_check_debug(err)

        fetchfiles = [f[0] for f in needed]
        fetchfiles.sort()

        # In the clean scan, contrib/a* should be present.
        self.assertTrue(self._path_in_list('contrib/ada', full_scanfiles))
        self.assertTrue(self._path_in_list('contrib/amd64', full_scanfiles))
        # In the -X scan, contrib/a* should be absent.
        self.assertFalse(self._path_in_list('contrib/ada', scanfiles))
        self.assertFalse(self._path_in_list('contrib/amd64', scanfiles))
        # In the fetch, contrib/a* should be absent.
        self.assertFalse(self._path_in_list('contrib/ada', fetchfiles))
        self.assertFalse(self._path_in_list('contrib/amd64', fetchfiles))

        self.assertNotEquals(full_scanfiles, fetchfiles)
        self.assertEquals(scanfiles, fetchfiles)

    def test_e2e_excludeglob_src1(self):
        '''
        Run a transfer with src -X glob, check the directory is excluded.
        '''
        self._unpack_tarball(self.in_tmp, self.zlib_tarball)
        zlibsrc = os.path.join(self.in_tmp, 'zlib-1.2.8')
        zlibdst = os.path.join(self.out_tmp, 'zlib-1.2.8')

        # Run a full scan.
        (out, err) = self._check_grab_hsync('-S %s -z --scan-debug'
                                            % zlibsrc)
        full_scanlist = self._get_scan_debug(err)

        full_scanfiles = [f[0] for f in full_scanlist]
        full_scanfiles.sort()

        # Run a scan excluding the watcom/ directory.
        (out, err) = self._check_grab_hsync('-S %s -z -X wat* --scan-debug'
                                            % zlibsrc)
        scanlist = self._get_scan_debug(err)

        # Run hsync -D to fetch without watcom/.
        (out, err) = self._check_grab_hsync('-D %s -u %s -Z --check-debug' %
                                            (zlibdst, zlibsrc))
        (needed, not_needed) = self._get_check_debug(err)

        # Check we fetched the exact files we expected to fetch.
        scanfiles = [f[0] for f in scanlist]
        scanfiles.sort()

        fetchfiles = [f[0] for f in needed]
        fetchfiles.sort()

        # Fetch should match the second scan (with -X)
        self.assertNotEquals(full_scanfiles, fetchfiles)
        self.assertEquals(scanfiles, fetchfiles)

        # In the clean scan, watcom/ should be present.
        self.assertTrue(self._path_in_list('watcom/', full_scanfiles))
        # In the -X scan, watcom/ should be absent.
        self.assertFalse(self._path_in_list('watcom/', scanfiles))
        # In the fetch, watcom/ should be absent.
        self.assertFalse(self._path_in_list('watcom/', fetchfiles))

    def test_e2e_excludeglob_src2(self):
        '''
        Run a transfer with src -X glob subdir, check the directory is
        excluded.
        '''
        self._unpack_tarball(self.in_tmp, self.zlib_tarball)
        zlibsrc = os.path.join(self.in_tmp, 'zlib-1.2.8')
        zlibdst = os.path.join(self.out_tmp, 'zlib-1.2.8')

        # Run a full scan.
        (out, err) = self._check_grab_hsync('-S %s -z --scan-debug'
                                            % zlibsrc)
        full_scanlist = self._get_scan_debug(err)

        full_scanfiles = [f[0] for f in full_scanlist]
        full_scanfiles.sort()

        # Run a scan excluding the contrib/amd64 directory.
        (out, err) = self._check_grab_hsync('-S %s -z -X contrib/amd64 '
                                            '--scan-debug'
                                            % zlibsrc)
        scanlist = self._get_scan_debug(err)

        # Run hsync -D to fetch without contrib/amd64.
        (out, err) = self._check_grab_hsync('-D %s -u %s -Z --check-debug' %
                                            (zlibdst, zlibsrc))
        (needed, not_needed) = self._get_check_debug(err)

        # Check we fetched the exact files we expected to fetch.
        scanfiles = [f[0] for f in scanlist]
        scanfiles.sort()

        fetchfiles = [f[0] for f in needed]
        fetchfiles.sort()

        # Fetch should match the second scan (with -X)
        self.assertNotEquals(full_scanfiles, fetchfiles)
        self.assertEquals(scanfiles, fetchfiles)

        # In the clean scan, contrib/amd64/ should be present.
        self.assertTrue(self._path_in_list('contrib/amd64/', full_scanfiles))
        # In the -X scan, contrib/amd64/ should be absent.
        self.assertFalse(self._path_in_list('contrib/amd64/', scanfiles))
        # In the fetch, contrib/amd64/ should be absent.
        self.assertFalse(self._path_in_list('contrib/amd64/', fetchfiles))