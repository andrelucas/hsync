# Functional tests for hsync
#
# Call out to the script, no running main() directly.

from __future__ import print_function

import inspect
import logging
import os
import re
import shutil
from subprocess import *
#import sys
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

    def _check_grab_hsync(self, opts, expected_ret=0):
        (ret, out, err) = self._grab_hsync(opts)
        self.assertEquals(ret, expected_ret)
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

    def _get_fetch_debug(self, err):
        return (self.__get_debug(err, "fetch i_fetched"),
                self.__get_debug(err, "fetch i_not_fetched"))

    def _path_in_list(self, path, flist):
        # Assert that a path is found in the given filelist.
        for fpath in flist:
            if fpath.startswith(path):
                log.debug("_path_in_list: '%s' matches '%s'", fpath, path)
                return True

        return False

    def test_e2e_simple1(self):
        '''Run a simple end-to-end transfer'''
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

        checkfiles = [f[0] for f in needed]
        checkfiles.sort()
        self.assertEquals(scanfiles, checkfiles)

    def test_e2e_contents_error_continue(self):
        '''Check we get meaningful errors'''
        self._unpack_tarball(self.in_tmp, self.zlib_tarball)
        zlibsrc = os.path.join(self.in_tmp, 'zlib-1.2.8')
        zlibdst = os.path.join(self.out_tmp, 'zlib-1.2.8')
        (out, err) = self._check_grab_hsync('-S %s -z --scan-debug' % zlibsrc)
        scanlist = self._get_scan_debug(err)

        # Deliberately make the contents fetch fail.
        nerfed_file = 'README'
        os.unlink(os.path.join(zlibsrc, nerfed_file))

        (out, err) = self._check_grab_hsync('-D %s -u %s -Z '
                                            '--check-debug --fetch-debug' %
                                            (zlibdst, zlibsrc),
                                            expected_ret=1)
        (needed, not_needed) = self._get_check_debug(err)
        #print("err: %s" % err, file=sys.stderr)
        (fetched, not_fetched) = self._get_fetch_debug(err)

        re_errcheck = re.compile(
            r"Failed to retrieve '[^']+/%s'" % nerfed_file)
        self.assertIsNotNone(re_errcheck.search(err, re.MULTILINE))

        # Check we tried to fetch the exact files we expected to fetch.
        scanfiles = [f[0] for f in scanlist]
        scanfiles.sort()
        checkfiles = [f[0] for f in needed]
        checkfiles.sort()
        self.assertEquals(scanfiles, checkfiles)

        # Check we actually fetched the files we expected - we'll fail to
        # fetch the nerfed file, check that's true.
        fetchfiles = [f[0] for f in fetched]
        fetchfiles.sort()
        self.assertNotEquals(scanfiles, fetchfiles)
        scanfiles_sans_nerf = [f for f in scanfiles if f != nerfed_file]
        self.assertEquals(scanfiles_sans_nerf, fetchfiles)
        notfetchfiles = [f[0] for f in not_fetched]
        notfetchfiles.sort()
        self.assertEquals(notfetchfiles, [nerfed_file])

    def test_e2e_exclude_dst1(self):
        '''
        Transfer with dest -X, check the directory is excluded.
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
        Transfer with dest -X subdir, check the directory is excluded.
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
        '''Transfer with src -X, check the directory is excluded.'''
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
        Transfer with src -X subdir, check the directory is
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
        Transfer with dest -X glob, check the directory is excluded.
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
        Transfer with dest -X glob in subdir, check the right
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
        Transfer with src -X glob, check the directory is excluded.
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
        Transfer with src -X glob subdir, check the directory is
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

    def test_e2e_nodelete1(self):
        '''
        Transfer check --no-delete on/off.

        Delete some stuff in the source, re-run the source side then the dest
        side.

        Check the files are not deleted in the dest with --no-delete active.

        Re-run the dest side without --no-delete, check the files are gone.
        '''

        self._unpack_tarball(self.in_tmp, self.zlib_tarball)
        zlibsrc = os.path.join(self.in_tmp, 'zlib-1.2.8')
        zlibdst = os.path.join(self.out_tmp, 'zlib-1.2.8')

        # Run a full scan.
        (out, err) = self._check_grab_hsync('-S %s -z --scan-debug'
                                            % zlibsrc)
        complete_scanlist = self._get_scan_debug(err)

        complete_scanfiles = [f[0] for f in complete_scanlist]
        complete_scanfiles.sort()

        # Run hsync -D to fetch everything.
        (out, err) = self._check_grab_hsync('-D %s -u %s -Z --check-debug' %
                                            (zlibdst, zlibsrc))

        (needed, not_needed) = self._get_check_debug(err)
        complete_fetchfiles = [f[0] for f in needed]
        complete_fetchfiles.sort()

        # Simple e2e fetch should match.
        self.assertEquals(complete_scanfiles, complete_fetchfiles)

        # Get a list of the files we'll delete in the src.
        srcdel = [f for f in complete_scanfiles if f.startswith('watcom')]

        # Now delete some files.
        shutil.rmtree(os.path.join(zlibsrc, 'watcom'))

        # Run a full scan.
        (out, err) = self._check_grab_hsync('-S %s -z --scan-debug'
                                            % zlibsrc)
        del_scanlist = self._get_scan_debug(err)

        del_scanfiles = [f[0] for f in del_scanlist]
        del_scanfiles.sort()

        # Check something's changed.
        self.assertNotEquals(complete_scanfiles, del_scanfiles)
        self.assertTrue(self._path_in_list('watcom', complete_scanfiles))
        self.assertFalse(self._path_in_list('watcom', del_scanfiles))

        # Re-run -D in --no-delete mode - should stay the same.
        (out, err) = self._check_grab_hsync('-D %s -u %s -Z --check-debug '
                                            '--no-delete' %
                                            (zlibdst, zlibsrc))

        (needed, not_needed) = self._get_check_debug(err)
        nodel_fetchfiles = [f[0] for f in needed]
        nodel_fetchfiles.sort()
        nodel_delfiles = [f[0] for f in not_needed]
        nodel_delfiles.sort()

        # not_needed will have the deletions...
        self.assertNotEquals(nodel_delfiles, [])
        self.assertTrue(self._path_in_list('watcom', nodel_delfiles))
        # But all the files *must* still be there.
        for f in srcdel:
            self.assertTrue(os.path.exists(os.path.join(zlibdst, f)))

        # Now re-run -D without --no-delete and check they're gone.
        (out, err) = self._check_grab_hsync('-D %s -u %s -Z --check-debug ' %
                                            (zlibdst, zlibsrc))

        (needed, not_needed) = self._get_check_debug(err)
        del_fetchfiles = [f[0] for f in needed]
        del_fetchfiles.sort()
        del_delfiles = [f[0] for f in not_needed]
        del_delfiles.sort()

        # Check we're in sync.
        for f in srcdel:
            self.assertTrue(f in del_delfiles)
        for f in del_delfiles:
            self.assertTrue(f in srcdel)

        self.assertTrue(del_fetchfiles, [])
        for f in srcdel:
            self.assertFalse(os.path.exists(os.path.join(zlibdst, f)))

    def test_e2e_include_dst1(self):
        '''
        Run a transfer with dest -I, check that only the listed directory is
        included.
        '''
        self._unpack_tarball(self.in_tmp, self.zlib_tarball)
        zlibsrc = os.path.join(self.in_tmp, 'zlib-1.2.8')
        zlibdst = os.path.join(self.out_tmp, 'zlib-1.2.8')

        # Run a full scan.
        (out, err) = self._check_grab_hsync('-S %s -z --scan-debug'
                                            % zlibsrc)
        scanlist = self._get_scan_debug(err)

        scanfiles = [f[0] for f in scanlist]
        scanfiles.sort()

        # Run hsync -D to fetch without watcom/.
        (out, err) = self._check_grab_hsync('-D %s -u %s -Z '
                                            '--check-debug --fetch-debug'
                                            ' -I watcom' %
                                            (zlibdst, zlibsrc))
        (needed, not_needed) = self._get_check_debug(err)
        (i_fetched, i_not_fetched) = self._get_fetch_debug(err)

        full_fetchfiles = [f[0] for f in needed]
        full_fetchfiles.sort()

        # Fetch should match the first scan (with -X), but not the full scan
        # as watcom/ files should not be transferred.
        self.assertEquals(scanfiles, full_fetchfiles)

        # See what we actually fetched.
        did_fetch = [f[0] for f in i_fetched]
        did_not_fetch = [f[0] for f in i_not_fetched]

        for f in did_fetch:
            self.assertTrue(f.startswith('watcom'))

        for f in did_not_fetch:
            self.assertFalse(f.startswith('watcom'))

    def test_e2e_include_glob_dst1(self):
        '''
        Run a transfer with dest -I glob, check that only the listed directory
        is included.
        '''
        self._unpack_tarball(self.in_tmp, self.zlib_tarball)
        zlibsrc = os.path.join(self.in_tmp, 'zlib-1.2.8')
        zlibdst = os.path.join(self.out_tmp, 'zlib-1.2.8')

        # Run a full scan.
        (out, err) = self._check_grab_hsync('-S %s -z --scan-debug'
                                            % zlibsrc)
        scanlist = self._get_scan_debug(err)

        scanfiles = [f[0] for f in scanlist]
        scanfiles.sort()

        # Run hsync -D to fetch without watcom/.
        (out, err) = self._check_grab_hsync('-D %s -u %s -Z '
                                            '--check-debug --fetch-debug'
                                            ' -I wat*' %
                                            (zlibdst, zlibsrc))
        (needed, not_needed) = self._get_check_debug(err)
        (i_fetched, i_not_fetched) = self._get_fetch_debug(err)

        full_fetchfiles = [f[0] for f in needed]
        full_fetchfiles.sort()

        # Fetch should match the first scan (with -X), but not the full scan
        # as watcom/ files should not be transferred.
        self.assertEquals(scanfiles, full_fetchfiles)

        # See what we actually fetched.
        did_fetch = [f[0] for f in i_fetched]
        did_not_fetch = [f[0] for f in i_not_fetched]

        for f in did_fetch:
            self.assertTrue(f.startswith('watcom'))

        for f in did_not_fetch:
            self.assertFalse(f.startswith('watcom'))

    def test_e2e_implicit_ignore_dirs_src1(self):
        '''Check implicitly-excluded dirs'''

        for xdir in ('.git', '.svn', 'CVS',
                     'd/.git', 'd/.svn', 'd/CVS'):
            log.debug("Testing --no-ignore-dirs for '%s'", xdir)

            self._just_remove(self.in_tmp)
            os.makedirs(self.in_tmp)
            self._unpack_tarball(self.in_tmp, self.zlib_tarball)
            zlibsrc = os.path.join(self.in_tmp, 'zlib-1.2.8')

            # Makedirs will make any parent directories for us.
            xdirsrc = os.path.join(zlibsrc, xdir)
            os.makedirs(xdirsrc)
            self.assertTrue(os.path.isdir(xdirsrc))

            # Run a full scan.
            (out, err) = self._check_grab_hsync('-S %s -z --scan-debug -d'
                                                % zlibsrc)
            dflt_scanlist = self._get_scan_debug(err)

            dflt_scanfiles = [f[0] for f in dflt_scanlist]
            dflt_scanfiles.sort()

            # Now run a new scan excluding the watcom/ directory.
            (out, err) = self._check_grab_hsync('-S %s -z --no-ignore-dirs '
                                                '--scan-debug -d'
                                                % zlibsrc)
            noex_scanlist = self._get_scan_debug(err)

            # Check we scanned the right files.
            dflt_scanfiles = [f[0] for f in dflt_scanlist]
            dflt_scanfiles.sort()

            noex_scanfiles = [f[0] for f in noex_scanlist]
            noex_scanfiles.sort()

            # In the clean scan, the xdir should be absent.
            self.assertFalse(self._path_in_list(xdir, dflt_scanfiles))
            # In the --no-ignore-files scan, the xdir should be present.
            self.assertTrue(self._path_in_list(xdir, noex_scanfiles))

    def test_e2e_implicit_ignore_files_src1(self):
        '''Check implicitly-excluded files'''

        for xfile in ('test.swp', 'test~', '.nfs00deadbeef',
                      'd/test.swp', 'd/test~', 'd/.nfs00deadbeef'):
            log.debug("Testing --no-ignore-files for '%s'", xfile)

            self._just_remove(self.in_tmp)
            os.makedirs(self.in_tmp)
            self._unpack_tarball(self.in_tmp, self.zlib_tarball)
            zlibsrc = os.path.join(self.in_tmp, 'zlib-1.2.8')

            xfilesrc = os.path.join(zlibsrc, xfile)
            if os.path.dirname(xfilesrc) != zlibsrc:
                xfiledir = os.path.join(zlibsrc, os.path.dirname(xfile))
                os.makedirs(xfiledir)

            with open(xfilesrc, 'w') as f:
                print('hello', file=f)

            self.assertTrue(os.path.isfile(xfilesrc))

            # Run a full scan.
            (out, err) = self._check_grab_hsync('-S %s -z --scan-debug -d'
                                                % zlibsrc)
            dflt_scanlist = self._get_scan_debug(err)

            dflt_scanfiles = [f[0] for f in dflt_scanlist]
            dflt_scanfiles.sort()

            # Now run a new scan excluding the watcom/ directory.
            (out, err) = self._check_grab_hsync('-S %s -z --no-ignore-files '
                                                '--scan-debug -d'
                                                % zlibsrc)
            noex_scanlist = self._get_scan_debug(err)

            # Check we scanned the right files.
            dflt_scanfiles = [f[0] for f in dflt_scanlist]
            dflt_scanfiles.sort()

            noex_scanfiles = [f[0] for f in noex_scanlist]
            noex_scanfiles.sort()

            # In the clean scan, the xdir should be absent.
            self.assertFalse(self._path_in_list(xfile, dflt_scanfiles),
                             "'%s' should be absent by default" % xfile)
            # In the --no-ignore-files scan, the xdir should be present.
            self.assertTrue(self._path_in_list(xfile, noex_scanfiles),
                            "'%s' should be present with --no-ignore-files" %
                            xfile)
