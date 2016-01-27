# README for Hsync

Hsync is designed to do rsync-style file tree synchronisation, but to transfer
only whole files in a way that can be scanned in-transit.

It goes to some trouble to minimise the amount of data transferred.

## In brief

Hsync trades higher CPU and memory use for minimal use of bandwidth. On the
server side, Hsync is run to generate a list of file metadata, and SHA256
signatures for file contents.

On the client side, Hsync pulls the server's signature file, compares it to any
signature file it may have stored from earlier runs, and then downloads the
files it needs to bring the client into agreement with the server. The SHA
signatures are checked before the downloaded file is moved into place.

By default, both client and server will use the modification time of files to
attempt to avoid file I/O. This is especially useful when the files are
mounted via NFS.

## Tutorial example

Task: Sync the source tree of zlib (unpacked from zlib-1.2.8.tar.gz) from one place
to another, ignoring the other obvious ways of doing so.

Assume the files are unpacked to `/var/www/zlib-1.2.8`, there's a web server
that publishes it at `http://127.0.0.1:28080/zlib-1.2.8/`, and files go to
`/var/tmp/out`.

### Server-side

    $ hsync -S /var/www/zlib-1.2.8
    Scanning source filesystem
	Generating signature file /var/www/zlib-1.2.8/HSYNC.SIG

Note that if you run it again, you get some slightly different output:

	hsync -S /var/www/zlib-1.2.8
	Reading existing hashfile
	F: HSYNC.SIG
	Scanning source filesystem (using pre-existing hash to reduce IO)
	Generating signature file /var/www/zlib-1.2.8/HSYNC.SIG

Hsync is trying to reduce the I/O load on the server side by reusing the
existing hashfile. You can turn this off with `--always-checksum`, but this
will be a significant I/O hit.

### Client-side

    $ hsync -D /var/tmp/out -u http://127.0.0.1:28080/zlib-1.2.8
    Fetching remote hashfile
	F: HSYNC.SIG
	Comparing local filesystem to signature file
	Caching scanned signature file /var/tmp/out/HSYNC.SIG
	F: CMakeLists.txt [object 1/272 (0%)]
	F: ChangeLog [object 2/272 (1%)]
	F: FAQ [object 3/272 (1%)]
	F: INDEX [object 4/272 (1%)]
	F: Makefile [object 5/272 (2%)]
	...
	F: zlib.h [object 266/272 (98%)]
	F: zlib.map [object 267/272 (98%)]
	F: zlib.pc.cmakein [object 268/272 (99%)]
	F: zlib.pc.in [object 269/272 (99%)]
	F: zlib2ansi [object 270/272 (99%)]
	F: zutil.c [object 271/272 (100%)]
	F: zutil.h [object 272/272 (100%)]
	Fetch completed
	Writing signature file /var/tmp/out/HSYNC.SIG
	$

This mirrors the server-side to /var/tmp/out, saving a copy of the hashfile to
save on I/O next time. Note that hsync saved `HSYNC.SIG` as soon as it
completed its local scan, as well as at the end when all files have been
transferred. This is to speed things up in the common case where a transfer is
interrupted, perhaps because it's taking too long.

As you might hope, running it again results in fewer transfers:

	$ hsync -D /var/tmp/out -u http://127.0.0.1:28080/zlib-1.2.8
	Fetching remote hashfile
	F: HSYNC.SIG
	Reading existing hashfile
	F: HSYNC.SIG
	Comparing local filesystem to signature file (using pre-existing hash to reduce IO)
	Caching scanned signature file /var/tmp/out/HSYNC.SIG
	Fetch completed
	Writing signature file /var/tmp/out/HSYNC.SIG

Actually, it results in no transfers except for the signature file, which it
has to transfer to know if anything has changed.

To reassure yourself that this is really doing something, delete and add some files:

	$ cp /bin/ls /var/tmp/out/
	$ rm /var/tmp/out/Makefile
	$ hsync -D /var/tmp/out -u http://127.0.0.1:28080/zlib-1.2.8
	Fetching remote hashfile
	F: HSYNC.SIG
	Reading existing hashfile
	F: HSYNC.SIG
	Comparing local filesystem to signature file (using pre-existing hash to reduce IO)
	Caching scanned signature file /var/tmp/out/HSYNC.SIG
	F: Makefile [object 1/1 (100%)]
	Fetch completed
	Remove file: ls
	Writing signature file /var/tmp/out/HSYNC.SIG
	$

As you might hope, this removed the file we added, and re-transferred the file we deleted.

If the _source_ changes, you must_ re-run `hsync -S`, or the changes will not
be reflected in the source-side `HSYNC.SIG` file and so will not be sync'd.
This is the step that will confuse _rsync_ users; there is no automatic
updating of the server side, at least not without a little web server magic.

[It's quite possible that the web server could be configured to run a
server-side scan when the HSYNC.SIG file is fetched. This is beyond the scope
of this article.]


## Useful options

`--version`

`--help` / `-h`

`-v` makes hsync more verbose.

`-d` makes hsync insanely verbose.

`-P` shows detailed progress information as hsync runs.

`-q` suppresses almost all output.

`--http-user`, `--http-pass` set the HTTP AUTH username and password.

`-X` / `--exclude-dir` removes a directory from consideration. Note this
ignores the file on the source/server, and stops it being sync'd on the
destination/client side.

