#!/usr/bin/env python

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

import grp
import logging
import os
import pwd

log = logging.getLogger()


class UidGidMapper(object):

    def __init__(self):
        self.uid_to_name = {}
        self.name_to_uid = {}
        self.gid_to_group = {}
        self.group_to_gid = {}

        self.missing_name_warned = set()
        self.missing_group_warned = set()
        self.missing_uid_warned = set()
        self.missing_gid_warned = set()

        self.default_uid = os.getuid()
        self.default_gid = os.getgid()

        # Let these throw KeyError - if we can't find our own username and
        # group given our own uid and gid, we're in bad shape.
        self.default_name = pwd.getpwuid(self.default_uid).pw_name
        self.default_group = grp.getgrgid(self.default_gid).gr_name

    def set_default_uid(self, uid):
        name = pwd.getpwuid(uid).pw_name
        self.default_uid = uid
        self.default_name = name

    def set_default_gid(self, gid):
        group = grp.getgrgid(gid).gr_name
        self.default_gid = gid
        self.default_group = group

    def set_default_name(self, name):
        uid = pwd.getpwnam(name).pw_uid
        self.default_name = name
        self.default_uid = uid

    def set_default_group(self, group):
        gid = grp.getgrnam(group).gr_gid
        self.default_group = group
        self.default_gid = gid

    def get_name_for_uid(self, uid):
        uid = int(uid)
        #log.debug("get_name_for_uid: uid %d", uid)
        if not uid in self.uid_to_name:
            try:
                name = pwd.getpwuid(uid).pw_name
            except KeyError:
                if not uid in self.missing_uid_warned:
                    log.warn("No name found for uid %d, setting "
                             "default username %s", uid, self.default_name)
                    self.missing_uid_warned.add(uid)
                    self.uid_to_name[uid] = self.default_name
                    return self.default_name

            self.uid_to_name[uid] = name
            self.name_to_uid[name] = uid

        #log.debug("uid %d name %s", uid, self.uid_to_name[uid])
        return self.uid_to_name[uid]

    def get_group_for_gid(self, gid):
        gid = int(gid)
        if not gid in self.gid_to_group:
            try:
                name = grp.getgrgid(gid).gr_name
                self.gid_to_group[gid] = name
                self.group_to_gid[name] = gid
            except KeyError:
                if not gid in self.missing_gid_warned:
                    log.warn("No group found for gid %d, setting "
                             "default group %s", gid, self.default_group)
                    self.missing_gid_warned.add(gid)
                    self.gid_to_group[gid] = self.default_group
                    return self.default_group

        return self.gid_to_group[gid]

    def get_uid_for_name(self, name):
        if not name is self.name_to_uid:
            uid = None
            try:
                uid = int(pwd.getpwnam(name).pw_uid)
                self.name_to_uid[name] = int(uid)
                self.uid_to_name[uid] = name
            except KeyError:
                if not name in self.missing_name_warned:
                    log.warn("No uid found for name %s, setting "
                             "default uid %d", name, self.default_uid)
                    self.missing_name_warned.add(name)
                    self.name_to_uid[name] = self.default_uid
                    return self.default_uid

        return self.name_to_uid[name]

    def get_gid_for_group(self, group):
        if not group in self.group_to_gid:
            gid = None
            try:
                gid = int(grp.getgrnam(group).gr_gid)
            except KeyError:
                if not group in self.missing_group_warned:
                    log.warn("No gid found for group %s, setting "
                             "default gid %d", group, self.default_gid)
                    self.missing_group_warned.add(group)
                    self.group_to_gid[group] = self.default_gid
                    return self.default_gid

            self.group_to_gid[group] = int(gid)
            self.gid_to_group[gid] = group

        return self.group_to_gid[group]
