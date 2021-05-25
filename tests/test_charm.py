# Copyright 2021 James Page
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import io
import json
import unittest

from unittest.mock import MagicMock

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


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(OpenApiaryCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.maxDiff = None

    def test_config_changed(self):
        # Check the initial Pebble plan is empty
        initial_plan = self.harness.get_container_pebble_plan("open-apiary")
        self.assertEqual(initial_plan.to_yaml(), "{}\n")
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
                        "LOG_LEVEL": "info",
                        "WEATHER_API_KEY": "",
                    },
                }
            }
        }

        # Get the open-apiary container from the model
        container = self.harness.model.unit.get_container("open-apiary")
        # NOTE(jamespage)
        # Mock out push and pull as not implemented in test harness
        container = self.harness.model.unit.get_container("open-apiary")
        container.push = MagicMock()
        container.pull = MagicMock()
        container.pull.return_value = io.StringIO(NODE_VERSION_INFO)

        self.harness.charm.on.config_changed.emit()
        # Everything happens on config-changed so just emit this event
        # Get the plan now we've run PebbleReady
        updated_plan = self.harness.get_container_pebble_plan(
            "open-apiary"
        ).to_dict()
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

        # Reset Mocks ready for next execution of config-changed
        container.push.reset_mock()
        container.pull.reset_mock()
        container.pull.return_value = io.StringIO(NODE_VERSION_INFO)

        self.harness.update_config({"weather-api-token": "mytoken"})
        updated_plan = self.harness.get_container_pebble_plan(
            "open-apiary"
        ).to_dict()
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
                        "LOG_LEVEL": "info",
                        "WEATHER_API_KEY": "mytoken",
                    },
                }
            }
        }
        self.assertEqual(expected_plan, updated_plan)
        container.push.assert_called_once_with(
            "/opt/app/config.json",
            json.dumps(
                self.harness.charm._open_apiary_config(),
                sort_keys=True,
                indent=2,
            ),
            make_dirs=True,
        )
        self.assertTrue(service.is_running())
        self.assertEqual(self.harness.model.unit.status, ActiveStatus())
        self.assertEqual(self.harness.get_workload_version(), "1.1.1")
