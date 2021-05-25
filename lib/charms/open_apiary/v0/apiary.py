"""Peer relation for Open Apiary charm

This class provides the implementation of the 'apiary' peer relation
used by the open-apiary charm.

The leader should use this interface to provide the shared JWT token
to other units in the application.

When the token has been provided, the interface will emit the 'token_available'
event which charms can then respond to.
"""

# The unique Charmhub library identifier, never change it
LIBID = "0e0479a91338413595db88baba97a23e"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 1

import logging

from ops.framework import EventBase, ObjectEvents, EventSource, Object


class TokenAvailableEvent(EventBase):
    """JWT Token Available Event"""

    pass


class ApiaryPeersEvents(ObjectEvents):
    """Events class for `on`"""

    token_available = EventSource(TokenAvailableEvent)


class ApiaryPeers(Object):
    """
    ApiaryPeers class
    """

    on = ApiaryPeersEvents()

    def __init__(self, charm, relation_name):
        super().__init__(charm, relation_name)
        self.charm = charm
        self.relation_name = relation_name
        self.framework.observe(
            self.charm.on[relation_name].relation_changed,
            self._on_apiary_relation_changed,
        )

    def _on_apiary_relation_changed(self, event) -> None:
        if self.jwt_token:
            logging.info("JWT token provided by leader, emitting event")
            self.on.token_available.emit()

    @property
    def jwt_token(self) -> str:
        return self.apiary.data[self.apiary.app].get("jwt-token")

    @property
    def apiary(self):
        """The relation associated with this interface"""
        return self.framework.model.get_relation(self.relation_name)

    def set_token(self, jwt_token):
        """Share JWT token with peers"""
        self.apiary.data[self.apiary.app]["jwt-token"] = jwt_token
