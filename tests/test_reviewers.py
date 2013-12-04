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

import unittest

import six

import reviewstats.cmd.reviewers


class ReviewersCSVTestCase(unittest.TestCase):
    def test_csv_rows(self):
        class Options(object):
            pass

        options = Options()
        options.csv_rows = 10
        reviewer_data = [('', '', '', '')] * 100
        sio = six.StringIO()

        reviewstats.cmd.reviewers.write_csv(reviewer_data, sio, options, {},
                                            {}, {}, {})

        # NOTE(russellb) With csv_rows set to 10, the output should have 11
        # lines: a heading line plus 10 rows
        self.assertEqual(sio.getvalue().count('\n'), 11)
