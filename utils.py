#
# Copyright (C) 2011 - Soren Hansen
# Copyright (C) 2013 - Red Hat, Inc.
#

# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import cPickle as pickle
import glob
import json
import paramiko
import os
import time


CACHE_AGE = 3600  # Seconds


def get_projects_info(project=None, all_projects=False):
    if all_projects:
        files = glob.glob('./*.json')
    else:
        files = [project]

    projects = []

    for fn in files:
        if os.path.isfile(fn):
            with open(fn, 'r') as f:
                project = json.loads(f.read())
                projects.append(project)

    return projects


def projects_q(project):
    return ('(' +
            ' OR '.join(['project:' + p for p in project['subprojects']]) +
            ')')


def get_changes(projects, ssh_user, ssh_key):
    all_changes = []

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.load_system_host_keys()

    for project in projects:
        changes = []

        pickle_fn = '%s-changes.pickle' % project['name']

        if os.path.isfile(pickle_fn):
            mtime = os.stat(pickle_fn).st_mtime
            if (time.time() - mtime) <= CACHE_AGE:
                with open(pickle_fn, 'r') as f:
                    changes = pickle.load(f)

        if len(changes) == 0:

            while True:
                client.connect('review.openstack.org', port=29418,
                        key_filename=ssh_key, username=ssh_user)
                cmd = ('gerrit query %s --all-approvals --patch-sets --format JSON' %
                       projects_q(project))
                if len(changes) > 0:
                    cmd += ' resume_sortkey:%s' % changes[-2]['sortKey']
                stdin, stdout, stderr = client.exec_command(cmd)
                for l in stdout:
                    changes += [json.loads(l)]
                if changes[-1]['rowCount'] == 0:
                    break

            with open(pickle_fn, 'w') as f:
                pickle.dump(changes, f)

        all_changes.extend(changes)

    return all_changes
