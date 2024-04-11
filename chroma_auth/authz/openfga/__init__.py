import json
import logging
import os
from typing import cast


from chromadb.auth import (
    AuthorizationContext,
    ServerAuthorizationConfigurationProvider,
    ServerAuthorizationProvider, AuthzResourceActions, AuthzResource, AuthzResourceTypes, AuthzAction,
)
from chromadb.auth.registry import register_provider, resolve_provider
from chromadb.config import System
from chromadb.telemetry.opentelemetry import (
    OpenTelemetryGranularity,
    trace_method,
)
from openfga_sdk import ClientConfiguration
from openfga_sdk.sync import OpenFgaClient
from openfga_sdk.client import ClientCheckRequest
from overrides import override
from chromadb.api import ServerAPI

logger = logging.getLogger(__name__)


@register_provider("openfga_config_provider")
class OpenFGAAuthorizationConfigurationProvider(
    ServerAuthorizationConfigurationProvider[ClientConfiguration]
):
    _config_file: str
    _config: ClientConfiguration

    def __init__(self, system: System) -> None:
        super().__init__(system)
        self._settings = system.settings
        if "FGA_API_URL" not in os.environ:
            raise ValueError("FGA_API_URL not set")
        self._config =  self._try_load_from_file()

        # TODO in the future we can also add credentials (preshared) or OIDC

    def _try_load_from_file(self)->ClientConfiguration:
        store_id = None
        model_id = None
        if "FGA_STORE_ID" in os.environ and "FGA_MODEL_ID" in os.environ:
            return ClientConfiguration(
                api_url=os.environ.get("FGA_API_URL"),
                store_id=os.environ["FGA_STORE_ID"],
                authorization_model_id=os.environ["FGA_MODEL_ID"],
            )
        if "FGA_CONFIG_FILE" not in os.environ and not store_id and not model_id:
            raise ValueError("FGA_CONFIG_FILE or FGA_STORE_ID/FGA_MODEL_ID env vars not set")
        with open(os.environ["FGA_CONFIG_FILE"], "r") as f:
            config = json.load(f)
            return ClientConfiguration(
                api_url=os.environ.get("FGA_API_URL"),
                store_id=config["store"]["id"],
                authorization_model_id=config["model"]["authorization_model_id"],
            )
    @override
    def get_configuration(self) -> ClientConfiguration:
        return self._config


@register_provider("openfga_authz_provider")
class OpenFGAAuthorizationProvider(ServerAuthorizationProvider):
    _authz_config_provider: ServerAuthorizationConfigurationProvider[ClientConfiguration]

    def __init__(self, system: System) -> None:
        super().__init__(system)
        self._settings = system.settings
        system.settings.require("chroma_server_authz_config_provider")
        self._api: ServerAPI = self._system.instance(ServerAPI)
        if self._settings.chroma_server_authz_config_provider:
            _cls = resolve_provider(
                self._settings.chroma_server_authz_config_provider,
                ServerAuthorizationConfigurationProvider,
            )
            self._authz_config_provider = cast(
                ServerAuthorizationConfigurationProvider[ClientConfiguration],
                self.require(_cls),
            )
        self._authz_to_model_action_map = {
            AuthzResourceActions.CREATE_DATABASE.value: "can_create_database",
            AuthzResourceActions.GET_DATABASE.value: "can_get_database",
            AuthzResourceActions.CREATE_TENANT.value: "can_create_tenant",
            AuthzResourceActions.GET_TENANT.value: "can_get_tenant",
            AuthzResourceActions.LIST_COLLECTIONS.value: "can_list_collections",
            AuthzResourceActions.COUNT_COLLECTIONS.value: "can_count_collections",
            AuthzResourceActions.GET_COLLECTION.value: "can_get_collection",
            AuthzResourceActions.CREATE_COLLECTION.value: "can_create_collection",
            AuthzResourceActions.GET_OR_CREATE_COLLECTION.value: "can_get_or_create_collection",
            AuthzResourceActions.DELETE_COLLECTION.value: "can_delete_collection",
            AuthzResourceActions.UPDATE_COLLECTION.value: "can_update_collection",
            AuthzResourceActions.ADD.value: "can_add_records",
            AuthzResourceActions.DELETE.value: "can_delete_records",
            AuthzResourceActions.GET.value: "can_get_records",
            AuthzResourceActions.QUERY.value: "can_query_records",
            AuthzResourceActions.COUNT.value: "can_count_records",
            AuthzResourceActions.UPDATE.value: "can_update_records",
            AuthzResourceActions.UPSERT.value: "can_upsert_records",
            AuthzResourceActions.RESET.value: "can_reset",
        }

        self._authz_to_model_object_map = {
            AuthzResourceTypes.DB.value: "database",
            AuthzResourceTypes.TENANT.value: "tenant",
            AuthzResourceTypes.COLLECTION.value: "collection",
        }

        logger.info(
            "Authorization Provider 'OpenFGAAuthorizationProvider' initialized"
        )


    def resolve_resource_action(self, resource: AuthzResource, action: AuthzAction) -> tuple:
        attrs = ""
        tenant = None,
        database = None
        if "tenant" in resource.attributes:
            attrs += f"{resource.attributes['tenant']}"
            tenant = resource.attributes['tenant']
        if "database" in resource.attributes:
            attrs += f"-{resource.attributes['database']}"
            database = resource.attributes['database']
        if action.id == AuthzResourceActions.GET_TENANT.value or action.id == AuthzResourceActions.CREATE_TENANT.value:
            return "server:localhost",self._authz_to_model_action_map[action.id]
        if action.id == AuthzResourceActions.GET_DATABASE.value or action.id == AuthzResourceActions.CREATE_DATABASE.value:
            return f"tenant:{attrs}",self._authz_to_model_action_map[action.id]
        if action.id == AuthzResourceActions.CREATE_COLLECTION.value:
            try:
                cole_exists =  self._api.get_collection(
                    resource.id, tenant=tenant, database=database
                )
                return f"collection:{attrs}-{cole_exists.name}",self._authz_to_model_action_map[AuthzResourceActions.GET_COLLECTION.value]
            except Exception as e:
                return f"{self._authz_to_model_object_map[resource.type]}:{attrs}",self._authz_to_model_action_map[action.id]
        if resource.id == "*":
            return f"{self._authz_to_model_object_map[resource.type]}:{attrs}",self._authz_to_model_action_map[action.id]
        else:
            return f"{self._authz_to_model_object_map[resource.type]}:{attrs}-{resource.id}",self._authz_to_model_action_map[action.id]
    @trace_method(
        "SimpleRBACAuthorizationProvider.authorize",
        OpenTelemetryGranularity.ALL,
    )
    @override
    def authorize(self, context: AuthorizationContext) -> bool:
        with OpenFgaClient(self._authz_config_provider.get_configuration()) as fga_client:
            try:
                obj,act = self.resolve_resource_action(resource=context.resource,action=context.action)
                resp = fga_client.check(body=ClientCheckRequest(
                    user=f"user:{context.user.id}",
                    relation=act,
                    object=obj,
                ))
                # openfga_sdk.models.check_response.CheckResponse
                return resp.allowed
            except Exception as e:
                logger.error(f"Error while authorizing: {str(e)}")
                return False

