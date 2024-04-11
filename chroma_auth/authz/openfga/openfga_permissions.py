import logging
from typing import cast

from chromadb.api.models import Collection
from chromadb.auth import ServerAuthorizationConfigurationProvider
from chromadb.auth.registry import resolve_provider
from chromadb.config import Component, System
from chromadb.server.fastapi import CreateTenant, CreateDatabase
from openfga_sdk import ListObjectsResponse, ClientConfiguration
from openfga_sdk.client.models import ClientTuple, ClientListObjectsRequest
from openfga_sdk.sync import OpenFgaClient
from starlette.requests import Request

logger = logging.getLogger(__name__)


class OpenFGAPermissionsAPI(Component):
    def __init__(self, system: System) -> None:
        super().__init__(system)
        self._settings = system.settings
        system.settings.require("chroma_server_authz_config_provider")
        _cls = resolve_provider(
            self._settings.chroma_server_authz_config_provider,
            ServerAuthorizationConfigurationProvider,
        )
        self._fga_configuration = cast(
            ServerAuthorizationConfigurationProvider[ClientConfiguration],
            self.require(_cls),
        ).get_configuration()

    def create_tenant_permissions(self, create: CreateTenant, request: Request) -> None:
        if not hasattr(request.state, "user_identity"):
            return
        identity = request.state.user_identity
        _object = f"tenant:{create.name}"
        _user = identity.attributes['team'] if identity.get_user_attributes() and hasattr(
            identity.get_user_attributes(), "team") else identity.get_user_id()
        with OpenFgaClient(self._fga_configuration) as fga_client:
            # Write the relationship tuple
            fga_client.write_tuples(
                body=[
                    ClientTuple(_user, "can_create_database", _object),
                    ClientTuple(_user, "can_get_database", _object)
                ]
            )

    def create_database_permissions(self, db: CreateDatabase, request: Request) -> None:
        if not hasattr(request.state, "user_identity"):
            return
        identity = request.state.user_identity  # automatically injected by the middleware: chromadb.auth.UserIdentity
        tenant = request.query_params.get("tenant")
        _object = f"database:{tenant}:{db.name}"
        _user = identity.attributes['team'] if identity.get_user_attributes() and hasattr(
            identity.get_user_attributes(), "team") else identity.get_user_id()
        with OpenFgaClient(self._fga_configuration) as fga_client:
            # Write the relationship tuple
            fga_client.write_tuples(
                body=[
                    ClientTuple(_user, "can_create_collection", _object),
                    ClientTuple(_user, "can_list_collections", _object),
                    ClientTuple(_user, "can_get_or_create_collection", _object),
                    ClientTuple(_user, "can_count_collections", _object),
                ]
            )

    def create_collection_permissions(self, collection: Collection, request: Request) -> None:
        if not hasattr(request.state, "user_identity"):
            return
        identity = request.state.user_identity  # AuthzUser
        tenant = request.query_params.get("tenant")
        database = request.query_params.get("database")
        _object = f"collection:{tenant}-{database}-{collection.id}"
        _object_for_get_collection = f"collection:{tenant}-{database}-{collection.name}"  # this is a bug in the Chroma Authz that feeds in the name of the collection instead of ID
        _user = f"team:{identity.get_user_attributes()['team']}#owner" if identity.get_user_attributes() and "team" in identity.get_user_attributes() else f"user:{identity.get_user_id()}"
        _user_writer = f"team:{identity.get_user_attributes()['team']}#writer" if identity.get_user_attributes() and "team" in identity.get_user_attributes() else None
        _user_reader = f"team:{identity.get_user_attributes()['team']}#reader" if identity.get_user_attributes() and "team" in identity.get_user_attributes() else None
        with OpenFgaClient(self._fga_configuration) as fga_client:
            fga_client.write_tuples(
                body=[
                    ClientTuple(_user, "can_add_records", _object),
                    ClientTuple(_user, "can_delete_records", _object),
                    ClientTuple(_user, "can_update_records", _object),
                    ClientTuple(_user, "can_get_records", _object),
                    ClientTuple(_user, "can_upsert_records", _object),
                    ClientTuple(_user, "can_count_records", _object),
                    ClientTuple(_user, "can_query_records", _object),
                    ClientTuple(_user, "can_get_collection", _object_for_get_collection),
                    ClientTuple(_user, "can_delete_collection", _object_for_get_collection),
                    ClientTuple(_user, "can_update_collection", _object),
                ]
            )
            if _user_writer:
                fga_client.write_tuples(
                    body=[
                        ClientTuple(_user_writer, "can_add_records", _object),
                        ClientTuple(_user_writer, "can_delete_records", _object),
                        ClientTuple(_user_writer, "can_update_records", _object),
                        ClientTuple(_user_writer, "can_get_records", _object),
                        ClientTuple(_user_writer, "can_upsert_records", _object),
                        ClientTuple(_user_writer, "can_count_records", _object),
                        ClientTuple(_user_writer, "can_query_records", _object),
                        ClientTuple(_user_writer, "can_get_collection", _object_for_get_collection),
                        ClientTuple(_user_writer, "can_delete_collection", _object_for_get_collection),
                        ClientTuple(_user_writer, "can_update_collection", _object),
                    ]
                )
            if _user_reader:
                fga_client.write_tuples(
                    body=[
                        ClientTuple(_user_reader, "can_get_records", _object),
                        ClientTuple(_user_reader, "can_query_records", _object),
                        ClientTuple(_user_reader, "can_count_records", _object),
                        ClientTuple(_user_reader, "can_get_collection", _object_for_get_collection),
                    ]
                )

    def delete_collection_permissions(self, collection: Collection, request: Request) -> None:
        if not hasattr(request.state, "user_identity"):
            return
        identity = request.state.user_identity

        _object = f"collection:{collection.tenant}-{collection.database}-{collection.id}"
        _object_for_get_collection = f"collection:{collection.tenant}-{collection.database}-{collection.name}"  # this is a bug in the Chroma Authz that feeds in the name of the collection instead of ID
        _user = f"team:{identity.get_user_attributes()['team']}#owner" if identity.get_user_attributes() and "team" in identity.get_user_attributes() else f"user:{identity.get_user_id()}"
        _user_writer = f"team:{identity.get_user_attributes()['team']}#writer" if identity.get_user_attributes() and "team" in identity.get_user_attributes() else None
        _user_reader = f"team:{identity.get_user_attributes()['team']}#reader" if identity.get_user_attributes() and "team" in identity.get_user_attributes() else None
        with OpenFgaClient(self._fga_configuration) as fga_client:
            fga_client.delete_tuples(
                body=[
                    ClientTuple(_user, "can_add_records", _object),
                    ClientTuple(_user, "can_delete_records", _object),
                    ClientTuple(_user, "can_update_records", _object),
                    ClientTuple(_user, "can_get_records", _object),
                    ClientTuple(_user, "can_upsert_records", _object),
                    ClientTuple(_user, "can_count_records", _object),
                    ClientTuple(_user, "can_query_records", _object),
                    ClientTuple(_user, "can_get_collection", _object_for_get_collection),
                    ClientTuple(_user, "can_delete_collection", _object_for_get_collection),
                    ClientTuple(_user, "can_update_collection", _object),
                ]
            )
            if _user_writer:
                fga_client.delete_tuples(
                    body=[
                        ClientTuple(_user_writer, "can_add_records", _object),
                        ClientTuple(_user_writer, "can_delete_records", _object),
                        ClientTuple(_user_writer, "can_update_records", _object),
                        ClientTuple(_user_writer, "can_get_records", _object),
                        ClientTuple(_user_writer, "can_upsert_records", _object),
                        ClientTuple(_user_writer, "can_count_records", _object),
                        ClientTuple(_user_writer, "can_query_records", _object),
                        ClientTuple(_user_writer, "can_get_collection", _object_for_get_collection),
                        ClientTuple(_user_writer, "can_delete_collection", _object_for_get_collection),
                        ClientTuple(_user_writer, "can_update_collection", _object),
                    ]
                )
            if _user_reader:
                fga_client.delete_tuples(
                    body=[
                        ClientTuple(_user_reader, "can_get_records", _object),
                        ClientTuple(_user_reader, "can_query_records", _object),
                        ClientTuple(_user_reader, "can_count_records", _object),
                        ClientTuple(_user_reader, "can_get_collection", _object_for_get_collection),
                    ]
                )
