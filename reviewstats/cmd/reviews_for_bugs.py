# Copyright 2013 Russell Bryant <rbryant@redhat.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


from argparse import ArgumentParser
import getpass
from launchpadlib.launchpad import Launchpad
import re

from reviewstats import utils


def main():
    parser = ArgumentParser(
        description="Get reviews for open bugs against a milestone")
    parser.add_argument(
        '-p', '--project', default='projects/nova.json',
        help='JSON file describing the project to generate stats for')
    parser.add_argument(
        '-m', '--milestone', default='',
        help='Only show bugs targeted to a specified milestone')
    parser.add_argument(
        '-u', '--user', default=getpass.getuser(), help='gerrit user')
    parser.add_argument('-k', '--key', default=None, help='ssh key for gerrit')

    args = parser.parse_args()

    projects = utils.get_projects_info(args.project, False)
    project_name = projects[0]['name']

    if not projects:
        print("Please specify a project.")
        return 1

    launchpad = Launchpad.login_with('openstack-releasing', 'production')
    proj = launchpad.projects[project_name]
    statuses = ['New', 'Incomplete', 'Confirmed', 'Triaged', 'In Progress']
    if args.milestone:
        milestone = proj.getMilestone(name=args.milestone)
        bugtasks = proj.searchTasks(status=statuses, milestone=milestone)
    else:
        bugtasks = proj.searchTasks(status=statuses)
    bugs_by_id = {}
    for bt in bugtasks:
        bugs_by_id[str(bt.bug.id)] = bt

    milestones = {}

    changes = utils.get_changes(projects, args.user, args.key, only_open=True)
    bug_regex = re.compile(r'bug/(\d+)')
    for change in changes:
        if 'topic' not in change:
            continue
        match = bug_regex.match(change['topic'])
        if not match:
            continue
        bugid = match.group(1)
        try:
            bugtask = bugs_by_id[bugid]
            milestone = str(bugtask.milestone).split('/')[-1]
            if milestone == 'None':
                milestone = 'Untargeted'
        except KeyError:
            milestone = 'Bug does not exist for this project'

        milestones.setdefault(milestone, [])
        milestones[milestone].append((change['url'], bugid))

    print('Reviews for bugs grouped by milestone for project: %s\n' % (
          project_name))

    for milestone, reviews in milestones.items():
        if args.milestone and milestone != args.milestone:
            continue
        print('Milestone: %s' % milestone)
        for review, bugid in reviews:
            print('--> %s -- https://bugs.launchpad.net/%s/+bug/%s' %
                  (review, project_name, bugid))
        print()
