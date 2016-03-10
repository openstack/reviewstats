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

from reviewstats.tests import base
from reviewstats import utils


class TestProjectInfo(base.TestCase):

    def test_project_definitions_load(self):
        utils.get_projects_info('', True)

    def test_get_projects_info_single_name(self):
        projects = utils.get_projects_info('nova')
        self.assertEqual(1, len(projects))

    def test_get_projects_info_single_name_projects_prefixed(self):
        projects = utils.get_projects_info('projects/stable.json')
        self.assertEqual(1, len(projects))
