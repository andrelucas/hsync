# Utilities that don't fit elsewhere.

import logging
import urlparse

log = logging.getLogger()


def cano_url(url, slash=False):
	'''
	Given a URL or bare file path, return a URL in a well-known form. File
	paths become file URLS, and (if requested) the URL is slash-terminated.
	'''

	log.debug("cano_url: %s", url)
	up = urlparse.urlparse(url)
	log.debug("urlparse: %s", up.geturl())
	if up.scheme == '':
	    url = 'file://' + url
	    log.debug("Add scheme, URL=%s", url)
	if slash and not url.endswith("/"):
	    url += "/"
	return url

