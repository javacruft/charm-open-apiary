#!/usr/bin/env python3
# Copyright 2021 James Page
# See LICENSE file for licensing details.

import hashlib
import json
import logging
import secrets

from charms.nginx_ingress_integrator.v0.ingress import IngressRequires
from charms.open_apiary.v0.apiary import ApiaryPeers, TokenAvailableEvent

from ops.charm import (
    CharmBase,
    RelationBrokenEvent,
    RelationChangedEvent,
    LeaderElectedEvent,
)
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus

logger = logging.getLogger(__name__)


def checksum_dict(data):
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, indent=2).encode()
    ).hexdigest()


class OpenApiaryCharm(CharmBase):
    """Charm the service."""

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.leader_elected, self._on_leader_elected)

        self.apiary = ApiaryPeers(self, "apiary")
        self.framework.observe(self.apiary.on.token_available, self._on_apiary_changed)

        self.framework.observe(
            self.on.mysql_database_relation_changed, self._on_db_changed
        )
        self.framework.observe(
            self.on.mysql_database_relation_broken, self._on_db_broken
        )
        self.ingress = IngressRequires(
            self,
            {
                "service-hostname": self.config["external-hostname"],
                "service-name": self.app.name,
                "service-port": 3000,
            },
        )
        self._stored.set_default(jwt_token=secrets.token_hex(16))
        self._stored.set_default(mysql_connection=None)

    def _on_leader_elected(self, event: LeaderElectedEvent) -> None:
        """Regenerate JWT token when new leader elected"""
        jwt_token = secrets.token_hex(16)
        self._stored.jwt_token = jwt_token
        self.apiary.set_token(jwt_token)
        self._on_config_changed(event)

    def _on_apiary_changed(self, event: TokenAvailableEvent) -> None:
        """Handle changes on peer relation to cluster"""
        if self.unit.is_leader():
            return
        self._stored.jwt_token = self.apiary.jwt_token
        self._on_config_changed(event)

    def _on_db_changed(self, event: RelationChangedEvent) -> None:
        """Handle connection to MySQL DB"""
        # TODO(jamespage)
        # refactor into interface library for more general use or
        # consume something more official from a mysql* operator
        mysql_connection = {
            "database": event.relation.data[event.unit].get("database"),
            "host": event.relation.data[event.unit].get("host"),
            "port": event.relation.data[event.unit].get("port", 3306),
            "username": event.relation.data[event.unit].get("user"),
            "password": event.relation.data[event.unit].get("password"),
        }
        if all(mysql_connection.values()):
            self._stored.mysql_connection = mysql_connection
        else:
            self._stored.mysql_connection = None
        self._on_config_changed(event)

    def _on_db_broken(self, event: RelationBrokenEvent) -> None:
        """Handle removal of relation to DB"""
        self._stored.mysql_connection = None
        self._on_config_changed(event)

    def _on_config_changed(self, event) -> None:
        """Define and start a workload using the Pebble API"""
        # NOTE(jamespage):
        # need to understand how config-change/relations get executed
        # if it applies to all sidecars at the same time there is a
        # chance that a service interuption will occur
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

        package_info = json.loads(container.pull("/opt/app/package.json").read())
        self.unit.set_workload_version(package_info.get("version"))

        self.ingress.update_config(
            {"service-hostname": self.config["external-hostname"]}
        )
        self.unit.status = ActiveStatus()

    def _open_apiary_layer(self) -> dict:
        """Generate Pebble Layer for Open Apiary"""
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
                        "LOG_DESTINATION": "/data/open-apiary.log",
                        "LOG_LEVEL": "debug" if self.config.get("debug") else "info",
                        "WEATHER_API_KEY": self.config.get("weather-api-token") or "",
                        # NOTE(jamespage): ugly but works - maybe push needs
                        # restart on change type integration to avoid this type of
                        # thing.
                        "CONFIG_CHECKSUM": checksum_dict(self._open_apiary_config()),
                    },
                }
            },
        }

    def _open_apiary_config(self) -> dict:
        """Generate configuration for Open Apiary"""
        db = {"type": "sqlite", "database": "/data/db.sql"}
        if self._stored.mysql_connection:
            db = {"type": "mysql"}
            db.update(self._stored.mysql_connection)
            logging.info("Configuring connection to remote MySQL DB")
        return {
            "db": db,
            "jwt": {"secret": self._stored.jwt_token},
        }


if __name__ == "__main__":
    main(OpenApiaryCharm, use_juju_for_storage=True)
