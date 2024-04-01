import importlib
import logging
from typing import Dict, cast, TypeVar, Optional

from chromadb.auth import (
    ServerAuthCredentialsProvider,
    AbstractCredentials,
    SimpleUserIdentity,
)
from chromadb.auth.registry import register_provider
from chromadb.config import System
from chromadb.telemetry.opentelemetry import (
    OpenTelemetryGranularity,
    trace_method,
    add_attributes_to_current_span,
)
from pydantic import SecretStr
from overrides import override

T = TypeVar("T")

logger = logging.getLogger(__name__)


@register_provider("multi_user_htpasswd_file")
class MultiUserHtpasswdFileServerAuthCredentialsProvider(ServerAuthCredentialsProvider):
    _creds: Dict[str, SecretStr]  # contains user:password-hash

    def __init__(self, system: System) -> None:
        super().__init__(system)
        try:
            self.bc = importlib.import_module("bcrypt")
        except ImportError:
            raise ValueError(
                "The bcrypt python package is not installed. "
                "Please install it with `pip install bcrypt`"
            )
        system.settings.require("chroma_server_auth_credentials_file")
        _file = str(system.settings.chroma_server_auth_credentials_file)
        self._creds = dict()
        with open(_file, "r") as f:
            for line in f:
                _raw_creds = [v for v in line.strip().split(":")]
                if len(_raw_creds) != 2:
                    raise ValueError(
                        "Invalid Htpasswd credentials found in "
                        f"[{str(system.settings.chroma_server_auth_credentials_file)}]. "
                        "Must be <username>:<bcrypt passwd>."
                    )
                self._creds[_raw_creds[0]] = SecretStr(_raw_creds[1])

    @trace_method(  # type: ignore
        "MultiUserHtpasswdFileServerAuthCredentialsProvider.validate_credentials",
        OpenTelemetryGranularity.ALL,
    )
    @override
    def validate_credentials(self, credentials: AbstractCredentials[T]) -> bool:
        _creds = cast(Dict[str, SecretStr], credentials.get_credentials())

        if len(_creds) != 2 or "username" not in _creds or "password" not in _creds:
            logger.error(
                "Returned credentials did match expected format: "
                "dict[username:SecretStr, password: SecretStr]"
            )
            add_attributes_to_current_span(
                {
                    "auth_succeeded": False,
                    "auth_error": "Returned credentials did match expected format: "
                    "dict[username:SecretStr, password: SecretStr]",
                }
            )
            return False  # early exit on wrong format
        _user_pwd_hash = (
            self._creds[_creds["username"].get_secret_value()]
            if _creds["username"].get_secret_value() in self._creds
            else None
        )
        validation_response = _user_pwd_hash is not None and self.bc.checkpw(
            _creds["password"].get_secret_value().encode("utf-8"),
            _user_pwd_hash.get_secret_value().encode("utf-8"),
        )
        add_attributes_to_current_span(
            {
                "auth_succeeded": validation_response,
                "auth_error": f"Failed to validate credentials for user {_creds['username'].get_secret_value()}"
                if not validation_response
                else "",
            }
        )
        return validation_response

    @override
    def get_user_identity(
        self, credentials: AbstractCredentials[T]
    ) -> Optional[SimpleUserIdentity]:
        _creds = cast(Dict[str, SecretStr], credentials.get_credentials())
        return SimpleUserIdentity(_creds["username"].get_secret_value())
