#!/usr/bin/env python
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

import calendar
import datetime
import optparse
import os
import os.path
import sys

import utils


def sec_to_period_string(seconds):
    days = seconds / (3600 * 24)
    hours = (seconds / 3600) - (days * 24)
    minutes = (seconds / 60) - (days * 24 * 60) - (hours * 60)
    return '%d days, %d hours, %d minutes' % (days, hours, minutes)


def get_age_of_patch(patch, now_ts):
    approvals = patch.get('approvals', [])
    approvals.sort(key=lambda a:a['grantedOn'])
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


def average_age(changes, key='age'):
    if not changes:
        return 0
    total_seconds = 0
    for change in changes:
        total_seconds += change[key]
    avg_age = total_seconds / len(changes)
    return sec_to_period_string(avg_age)


def median_age(changes, key='age'):
    if not changes:
        return 0
    changes = sorted(changes, key=lambda change: change[key])
    median_age = changes[len(changes)/2][key]
    return sec_to_period_string(median_age)


def number_waiting_more_than(changes, seconds, key='age'):
    index = 0
    for change in changes:
        if change[key] > seconds:
            return len(changes) - index
        index += 1
    return 0


def gen_stats(projects, waiting_on_reviewer, waiting_on_submitter,
        age_sorted, age2_sorted, age3_sorted, options):
    result = []
    result.append(('Projects', '%s' % [project['name']
                                      for project in projects]))
    stats = []
    stats.append(('Total Open Reviews', '%d' % (
            len(waiting_on_reviewer) + len(waiting_on_submitter))))
    stats.append(('Waiting on Submitter', '%d' % len(waiting_on_submitter)))
    stats.append(('Waiting on Reviewer', '%d' % len(waiting_on_reviewer)))
    stats.append(('Average wait time (latest revision)', '%s' % (
            average_age(waiting_on_reviewer))))
    stats.append(('Median wait time (latest revision)', '%s' % (
            median_age(waiting_on_reviewer))))
    stats.append(('Number waiting more than %i days (latest revision)' %
            options.waiting_more, '%i' % (number_waiting_more_than(
            age_sorted, 60 * 60 * 24 *
            options.waiting_more))))
    stats.append(('Average wait time (first revision)', '%s' % (
            average_age(waiting_on_reviewer, key='age2'))))
    stats.append(('Median wait time (first revision)', '%s' % (
            median_age(waiting_on_reviewer, key='age2'))))
    stats.append(('Average wait time (oldest without nack)', '%s' % (
            average_age(waiting_on_reviewer, key='age3'))))
    stats.append(('Median wait time (oldest without nack)', '%s' % (
            median_age(waiting_on_reviewer, key='age3'))))
    changes = []
    for change in age_sorted[-options.longest_waiting:]:
        changes.append('%s %s (%s)' % (sec_to_period_string(change['age']),
                                      change['url'], change['subject']))
    stats.append(('Longest waiting reviews (based on latest revision)',
                 changes))
    changes = []
    for change in age2_sorted[-options.longest_waiting:]:
       changes.append('%s %s (%s)' % (sec_to_period_string(change['age2']),
                                      change['url'], change['subject']))
    stats.append(('Longest waiting reviews (based on first revision)',
            changes))
    changes = []
    for change in age3_sorted[-options.longest_waiting:]:
       changes.append('%s %s (%s)' % (sec_to_period_string(change['age3']),
                                      change['url'], change['subject']))
    stats.append(('Longest waiting reviews (based on oldest rev without nack)',
            changes))

    result.append(stats)

    return result


def print_stats_txt(stats, f=sys.stdout):
    def print_list_txt(l, level):
        for item in l:
            if not isinstance(item, list):
                f.write('%s> ' % ('--' * level))
            print_item_txt(item, level)

    def print_item_txt(item, level):
        if isinstance(item, basestring):
            f.write('%s\n' % item)
        elif isinstance(item, list):
            print_list_txt(item, level + 1)
        elif isinstance(item, tuple):
            f.write('%s: ' % item[0])
            if isinstance(item[1], list):
                f.write('\n')
            print_item_txt(item[1], level)
        else:
            raise Exception('Unhandled type')

    print_list_txt(stats, 0)


def print_stats_html(stats, f=sys.stdout):
    def print_list_html(l, level):
        if level:
            f.write('<%s>\n' % ('ul' if level == 1 else 'ol'))
        for item in l:
            if level:
                f.write('%s<li>' % ('  ' * level))
            print_item_html(item, level)
            if level:
                f.write('</li>\n')
        if level:
            f.write('</%s>\n' % ('ul' if level == 1 else 'ol'))

    def print_item_html(item, level):
        if isinstance(item, basestring):
            f.write('%s' % item)
        elif isinstance(item, list):
            print_list_html(item, level + 1)
        elif isinstance(item, tuple):
            f.write('%s: ' % item[0])
            if isinstance(item[1], list):
                f.write('\n')
            print_item_html(item[1], level)
        else:
            raise Exception('Unhandled type')

    f.write('<html>\n')
    f.write('<head><title>Open Reviews for %s</title></head>\n' % stats[0][1])
    print_list_html(stats, 0)
    f.write('</html>\n')


def find_oldest_no_nack(change):
    last_patch = None
    for patch in reversed(change['patchSets']):
        nacked = False
        for review in patch.get('approvals', []):
            if review['type'] not in ('CRVW', 'VRIF'):
                continue
            if review['value'] in ('-1', '-2'):
                nacked = True
                break
        if nacked:
            break
        last_patch = patch
    return last_patch



def main(argv=None):
    if argv is None:
        argv = sys.argv

    optparser = optparse.OptionParser()
    optparser.add_option('-p', '--project', default='projects/nova.json',
            help='JSON file describing the project to generate stats for')
    optparser.add_option('-a', '--all', action='store_true',
            help='Generate stats across all known projects (*.json)')
    optparser.add_option('-u', '--user', default='russellb', help='gerrit user')
    optparser.add_option('-k', '--key', default=None, help='ssh key for gerrit')
    optparser.add_option('-s', '--stable', action='store_true',
            help='Include stable branch commits')
    optparser.add_option('-l', '--longest-waiting', type='int', default=5,
            help='Show n changesets that have waited the longest)')
    optparser.add_option('-m', '--waiting-more', type='int', default=7,
            help='Show number of changesets that have waited more than n days)')
    optparser.add_option('-H', '--html', action='store_true',
            help='Use HTML output instead of plain text')

    options, args = optparser.parse_args()

    projects = utils.get_projects_info(options.project, options.all)

    if not projects:
        print "Please specify a project."
        sys.exit(1)

    changes = utils.get_changes(projects, options.user, options.key,
            only_open=True)

    waiting_on_submitter = []
    waiting_on_reviewer = []

    now = datetime.datetime.utcnow()
    now_ts = calendar.timegm(now.timetuple())

    for change in changes:
        if 'rowCount' in change:
            continue
        if not options.stable and 'stable' in change['branch']:
            continue
        if change['status'] != 'NEW':
            # Filter out WORKINPROGRESS
            continue
        latest_patch = change['patchSets'][-1]
        waiting_for_review = True
        approvals = latest_patch.get('approvals', [])
        approvals.sort(key=lambda a:a['grantedOn'])
        for review in approvals:
            if review['type'] not in ('CRVW', 'VRIF'):
                continue
            if review['value'] in ('-1', '-2'):
                waiting_for_review = False
                break

        change['age'] = get_age_of_patch(latest_patch, now_ts)
        change['age2'] = get_age_of_patch(change['patchSets'][0], now_ts)
        patch = find_oldest_no_nack(change)
        change['age3'] = get_age_of_patch(patch, now_ts) if patch else 0

        if waiting_for_review:
            waiting_on_reviewer.append(change)
        else:
            waiting_on_submitter.append(change)

    age_sorted = sorted(waiting_on_reviewer, key=lambda change: change['age'])

    age2_sorted = sorted(waiting_on_reviewer, key=lambda change: change['age2'])

    age3_sorted = sorted(waiting_on_reviewer, key=lambda change: change['age3'])

    stats = gen_stats(projects, waiting_on_reviewer, waiting_on_submitter,
                age_sorted, age2_sorted, age3_sorted, options)

    if options.html:
        print_stats_html(stats)
    else:
        print_stats_txt(stats)


if __name__ == '__main__':
    sys.exit(main())
