#!/usr/bin/env python

import grp
import logging
import pwd

log = logging.getLogger()

class UidGidMapper(object):

    uid_to_name = {}
    name_to_uid = {}
    gid_to_name = {}
    name_to_gid = {}

    def get_name_for_uid(self, uid):
        if not uid in self.uid_to_name:
            name = pwd.getpwuid(uid).pw_name
            self.uid_to_name[uid] = name
            self.name_to_uid[name]  = uid
        return self.uid_to_name[uid]

    
    def get_name_for_gid(self, gid):
        if not gid in self.gid_to_name:
            name = grp.getgrgid(gid).gr_name
            self.gid_to_name[gid] = name
            self.name_to_gid[name] = gid
        return self.gid_to_name[gid]


    def get_uid_for_name(self, name):
        if not name is self.name_to_uid:
            uid = int(pwd.getpwnam(name).pw_uid)
            self.name_to_uid[name] = uid
            self.uid_to_name[uid] = name
        return self.name_to_uid[name]


    def get_gid_for_name(self, group):
        if not group in self.name_to_gid:
            gid = int(grp.getgrnam(group).gr_gid)
            self.name_to_gid[group] = gid
            self.gid_to_name[gid] = group
        return self.name_to_gid[group]
