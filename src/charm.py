#!/usr/bin/env python3
# Copyright 2021 James Page
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

    https://discourse.charmhub.io/t/4208
"""

import json
import logging

from charms.nginx_ingress_integrator.v0.ingress import IngressRequires

from ops.charm import CharmBase
from ops.main import main
from ops.model import ActiveStatus

logger = logging.getLogger(__name__)


class OpenApiaryCharm(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.ingress = IngressRequires(
            self,
            {
                "service-hostname": "open-apiary.juju",
                "service-name": self.app.name,
                "service-port": 3000,
            },
        )

    def _on_config_changed(self, event):
        """Define and start a workload using the Pebble API"""
        container = self.unit.get_container("open-apiary")
        layer = self._open_apiary_layer()
        services = container.get_plan().to_dict().get("services", {})
        if services != layer["services"]:
            container.add_layer("open-apiary", layer, combine=True)
            logging.info("Added updated layer 'open-apiary' to Pebble plan")
            if container.get_service("open-apiary").is_running():
                container.stop("open-apiary")
            container.push(
                "/opt/app/config.json",
                json.dumps(self._open_apiary_config(), sort_keys=True, indent=2),
                make_dirs=True,
            )
            container.start("open-apiary")
            logging.info("Restarted open_apiary service")
        self.unit.status = ActiveStatus()

    def _open_apiary_layer(self):
        return {
            "summary": "Open Apiary layer",
            "description": "pebble config layer for Open Apiary",
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
                        "LOG_DESTINATION": "stdout",
                        "LOG_LEVEL": "info",
                        "WEATHER_API_KEY": self.config.get("weather-api-key", ""),
                    },
                }
            },
        }

    def _open_apiary_config(self):
        return {
            "db": {"type": "sqlite", "database": "/data/db.sql"},
            "jwt": {"secret": "some-secret"},
        }


if __name__ == "__main__":
    main(OpenApiaryCharm)
