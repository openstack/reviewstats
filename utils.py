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
import logging
import os
import time

import paramiko

CACHE_AGE = 3600  # Seconds

LOG = logging.getLogger(__name__)


def get_projects_info(project=None, all_projects=False, base_dir='./projects'):
    if all_projects:
        files = glob.glob('%s/*.json' % base_dir)
    else:
        files = [project]

    projects = []

    for fn in files:
        if os.path.isfile(fn):
            with open(fn, 'r') as f:
                try:
                    project = json.loads(f.read())
                except Exception:
                    LOG.error('Failed to parse %s' % fn)
                    raise
                if not (all_projects and project.get('unofficial')):
                    projects.append(project)

    return projects


def projects_q(project):
    return ('(' +
            ' OR '.join(['project:' + p for p in project['subprojects']]) +
            ')')


def get_changes(projects, ssh_user, ssh_key, only_open=False,
                server='review.openstack.org'):
    all_changes = []

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    for project in projects:
        changes = []
        logging.debug('Getting changes for project %s' % project['name'])

        if not only_open:
            # Only use the cache for *all* changes (the entire history).
            # Requesting only the open changes isn't nearly as big of a deal,
            # so just get the current data.
            pickle_fn = '.%s-changes.pickle' % project['name']

            if os.path.isfile(pickle_fn):
                mtime = os.stat(pickle_fn).st_mtime
                if (time.time() - mtime) <= CACHE_AGE:
                    with open(pickle_fn, 'r') as f:
                        changes = pickle.load(f)

        if not changes:
            while True:
                client.connect(server, port=29418,
                               key_filename=ssh_key, username=ssh_user)
                cmd = ('gerrit query %s --all-approvals --patch-sets '
                       '--format JSON' % projects_q(project))
                if only_open:
                    cmd += ' status:open'
                if changes:
                    cmd += ' resume_sortkey:%s' % changes[-2]['sortKey']
                stdin, stdout, stderr = client.exec_command(cmd)
                for l in stdout:
                    changes += [json.loads(l)]
                if changes[-1]['rowCount'] == 0:
                    break

            if not only_open:
                with open(pickle_fn, 'w') as f:
                    pickle.dump(changes, f)

        all_changes.extend(changes)

    return all_changes


def patch_set_approved(patch_set):
    approvals = patch_set.get('approvals', [])
    for review in approvals:
        if review['type'] == 'APRV':
            return True
    return False


def get_age_of_patch(patch, now_ts):
    approvals = patch.get('approvals', [])
    approvals.sort(key=lambda a: a['grantedOn'])
    # The createdOn timestamp on the patch isn't what we want.
    # It's when the patch was written, not submitted for review.
    # The next best thing in the data we have is the time of the
    # first review.  When all is working well, jenkins or smokestack
    # will comment within the first hour or two, so that's better
    # than the other timestamp, which may reflect that the code
    # was written many weeks ago, even though it was just recently
    # submitted for review.
    if approvals:
        return now_ts - approvals[0]['grantedOn']
    else:
        return now_ts - patch['createdOn']
