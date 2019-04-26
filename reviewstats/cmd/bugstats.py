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
import bisect
from datetime import datetime
from datetime import timedelta
import prettytable
import sys
from textwrap import dedent

from launchpadlib.launchpad import Launchpad
import pytz

from reviewstats import utils


offsets = {
    'critical': 1,
    'high': 2,
    'undecided': 3,
    'other': 4,
    'total': 5,
    'created': 6,
    'closed': 7,
    'criticaltags': 8,
    }


class Listener(object):

    def __init__(self, project_name, lp_projects):
        self.name = project_name
        self.lp_projects = lp_projects
        self.periods = []
        self.now = datetime.now(pytz.utc)

    def categorise_task(self, bug_task, bug):
        """Categorise a bug task.

        :param bug_task: The LP API BugTask object to categorise.
        :param bug: The LP API Bug object to categorise.

        Note that we accept tasks in any order - the current merging of
        different projects is done serially rather than iterating all projects
        concurrently, which leads to out of order observation.
        """
        pos = bisect.bisect_right(self.periods, [bug_task.date_created])
        if pos:
            pos -= 1
        else:
            # May need to extend self.periods left
            self._setup_periods(bug_task.date_created)
        period = self.periods[pos]
        assert period[0] <= bug_task.date_created, "%s < %s" % (
            period[0], bug_task.date_created)
        sys.stderr.write('.')
        period[offsets['created']] = period[offsets['created']] + 1
        # Generate some cheaply available transition dates.
        # We consider it triaged when it has a status change away from New.
        date_triaged = bug_task.date_left_new
        # Run through the periods the bug was in different states for.
        # Unless/until we start doing activity log searching (or perhaps we
        # need to do that and cache the results) we mis-aggregate e.g. we count
        # the bug as the same importance for all time periods after it is
        # triaged.
        one_week = timedelta(weeks=1)
        while pos < len(self.periods):
            period = self.periods[pos]
            period_start = period[0]
            period_end = period_start + one_week
            if bug.duplicate_of_link:
                # Can't determine any transitions reliably.
                period[offsets['closed']] = period[offsets['closed']] + 1
                return
            if bug_task.date_closed and bug_task.date_closed < period_start:
                return
            if date_triaged and date_triaged < period_end:
                # Untriaged
                severity = offsets['other']
            else:
                if "Critical" == bug_task.importance:
                    severity = offsets['critical']
                    period[offsets['criticaltags']].update(bug.tags)
                elif "High" == bug_task.importance:
                    severity = offsets['high']
                elif "Undecided" == bug_task.importance:
                    severity = offsets['undecided']
                else:
                    severity = offsets['other']
            period[offsets['total']] = period[offsets['total']] + 1
            period[severity] = period[severity] + 1
            if bug_task.date_closed and bug_task.date_closed >= period_start:
                period[offsets['closed']] = period[offsets['closed']] + 1
            pos += 1

    def _setup_periods(self, start_date):
        """Setup time periods we're going to report on.

        :param start_date: The earliest date we will see data for.

        After this function is called self.periods will be a list of lists each
        of which should contain: 'Period start', 'critical', 'high',
        'undecided', 'other', 'total', 'created', 'closed', 'critical-tags' -
        e.g.  [datetime(..), 0, 0, 0, 0, 0, 0, 0, {'foo', 'bar}].
        We create one period for each week from start_date to now.

        If called when periods has already been setup, this will create more
        rows as needed.
        """
        if self.periods and start_date == self.periods[0][0]:
            return
        self.periods.reverse()
        if not self.periods:
            self.periods = [[self.now, 0, 0, 0, 0, 0, 0, 0, set()]]
        while self.periods[-1][0] > start_date:
            self.periods.append(
                [self.periods[-1][0] - timedelta(weeks=1),
                 0, 0, 0, 0, 0, 0, 0, set()])
        self.periods.reverse()

    def summarise(self):
        """Return summary data about the project.

        :return: A generator of period data. Each period is a list of strings
            describing the start of the period, the number of critical, high,
            undecided, other open bugs, total open bugs, created in the period,
            closed in the period, and bug tags present on any critical bugs.
        """
        for period in self.periods:
            yield ([period[0].strftime('%Y-%m-%d')] +
                   period[1:-1] + [','.join(period[-1])])


def main():
    parser = ArgumentParser(
        description="Calculate some statistics about project bugs.",
        epilog=dedent("""\
            Known caveats:
            Historical data uses the current task metadata rather than
            historical values. This is primarily due to performance
            considerations with the LP API and may be rectified in future (e.g.
            by mirroring the data persistently). As an example, if a bug is
            currently set to 'critical', it will show as critical in all time
            periods rather than progressing through different categories as it
            is triaged.
            """))
    parser.add_argument(
        '-p', '--project', default='projects/nova.json',
        help='JSON file describing the project to generate stats for.')
    args = parser.parse_args()
    projects = utils.get_projects_info(args.project, False)
    lp_project_listeners = {}
    listeners = set()
    if not projects:
        sys.stderr.write('No projects found: please specify one or more.\n')
        return 1
    launchpad = Launchpad.login_with(
        'openstack-releasing', 'production', credentials_file='.lpcreds')

    for project in projects:
        lp_projects = project.get('lp_projects', [])
        if not lp_projects:
            print("Please specify a project.")
            return 1
        listener = Listener(project['name'], lp_projects)
        listeners.add(listener)
        for lp_project in project.get('lp_projects', []):
            lp_project_listeners.setdefault(lp_project, []).append(listener)

    statuses = ['New', 'Incomplete', 'Opinion', 'Invalid', "Won't Fix",
        'Confirmed', 'Triaged', 'In Progress', "Fix Committed", "Fix Released"]

    bugs_by_bug_link = {}
    for lp_project, receivers in lp_project_listeners.items():
        proj = launchpad.projects[lp_project]
        # Sort by id to make creating time periods easy.
        bugtasks = proj.searchTasks(status=statuses, order_by="id")
        for task in bugtasks:
            if task.bug_link not in bugs_by_bug_link:
                bugs_by_bug_link[task.bug_link] = task.bug
            bug = bugs_by_bug_link[task.bug_link]
            for receiver in receivers:
                receiver.categorise_task(task, bug)

    for listener in listeners:
        sys.stdout.write("Project: %s\n" % listener.name)
        sys.stdout.write("LP Projects: %s\n" % listener.lp_projects)
        table = prettytable.PrettyTable(
            ('Period', 'critical', 'high', 'undecided', 'other', 'total',
             'created', 'closed', 'critical-tags'))
        for period in listener.summarise():
            table.add_row(period)
        sys.stdout.write("%s\n" % table)
