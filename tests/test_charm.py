# Copyright 2021 James Page
# See LICENSE file for licensing details.

# TODO
# peer relation testing
# ingress testing and configuration option for hostname

import io
import json
import unittest

from unittest.mock import MagicMock, ANY

from charm import OpenApiaryCharm
from ops.model import ActiveStatus
from ops.testing import Harness


# Partial test fixture only
NODE_VERSION_INFO = """
{
  "name": "open-apiary",
  "version": "1.1.1",
  "description": "Apiary management software",
  "author": "Simon Emms",
  "private": true,
  "license": "MIT",
  "main": "./server/main"
}
"""

COMPLETE_MYSQL_DATA_BAG = {
    "database": "testdatabase",
    "host": "mysql-db-server",
    "port": 3306,
    "user": "testuser",
    "password": "foobar",
}

INCOMPLETE_MYSQL_DATA_BAG = {
    "database": "testdatabase",
}


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(OpenApiaryCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        # NOTE(jamespage)
        # Mock out push and pull as not implemented in test harness
        container = self.harness.model.unit.get_container("open-apiary")
        container.push = MagicMock()
        container.pull = MagicMock()
        # Use of a lambda here just makes sure everytime the pull method is
        # executed a new StringIO reader is created.
        container.pull.side_effect = lambda *args: io.StringIO(NODE_VERSION_INFO)
        self.addCleanup(container.push)
        self.addCleanup(container.pull)
        self.maxDiff = None

    def _test_config_changed(
        self, weather_token: str = None, debug: bool = False
    ) -> None:
        """Base config_changed test handler"""
        # Expected plan with default config
        expected_plan = {
            "services": {
                "open-apiary": {
                    "override": "replace",
                    "summary": "open-apiary",
                    "command": "/usr/local/bin/npm start",
                    "startup": "enabled",
                    "environment": {
                        "PORT": "3000",
                        "DATA_PATH": "/data",
                        "UPLOAD_PATH": "/uploads",
                        "LOG_DESTINATION": "/data/open-apiary.log",
                        "LOG_LEVEL": "debug" if debug else "info",
                        "WEATHER_API_KEY": weather_token or "",
                    },
                }
            }
        }

        # Get the open-apiary container from the model
        container = self.harness.model.unit.get_container("open-apiary")
        self.harness.update_config(
            {
                "weather-api-token": weather_token,
                "debug": debug,
            }
        )
        # Everything happens on config-changed so just emit this event
        # Get the plan now we've run PebbleReady
        updated_plan = self.harness.get_container_pebble_plan("open-apiary").to_dict()
        # Check we've got the plan we expected
        self.assertEqual(expected_plan, updated_plan)
        # Check configuration file pushed to container
        container.push.assert_called_once_with(
            "/opt/app/config.json",
            json.dumps(
                self.harness.charm._open_apiary_config(),
                sort_keys=True,
                indent=2,
            ),
            make_dirs=True,
        )

        # Check the service was started
        service = container.get_service("open-apiary")
        self.assertTrue(service.is_running())
        # Ensure we set an ActiveStatus with no message
        self.assertEqual(self.harness.model.unit.status, ActiveStatus())
        self.assertEqual(self.harness.get_workload_version(), "1.1.1")

    def test_config_changed(self):
        """config changed with default options"""
        self._test_config_changed()

    def test_config_changed_weather_token_set(self):
        """config changed with token and debug logging"""
        self._test_config_changed(weather_token="mytoken", debug=True)

    def test_mysql_relation(self):
        """mysql-database relation test"""
        relation_id = self.harness.add_relation("mysql-database", "mysql")
        self.harness.add_relation_unit(relation_id, "mysql/0")

        # Check incomplete data handling - should use sqlite
        self.harness.update_relation_data(
            relation_id, "mysql/0", INCOMPLETE_MYSQL_DATA_BAG
        )
        expected_oa_config = {
            "db": {"database": "/data/db.sql", "type": "sqlite"},
            "jwt": {"secret": ANY},
        }
        self.assertEqual(expected_oa_config, self.harness.charm._open_apiary_config())

        # Check complete data handling - should use mysql
        self.harness.update_relation_data(
            relation_id, "mysql/0", COMPLETE_MYSQL_DATA_BAG
        )
        expected_oa_config = {
            "db": {
                "database": "testdatabase",
                "host": "mysql-db-server",
                "password": "foobar",
                "port": 3306,
                "type": "mysql",
                "username": "testuser",
            },
            "jwt": {"secret": ANY},
        }
        self.assertEqual(expected_oa_config, self.harness.charm._open_apiary_config())

        # TODO(jamespage)
        # write relation removal tests once Harness supports this
