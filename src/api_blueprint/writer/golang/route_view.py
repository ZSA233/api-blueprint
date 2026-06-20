from __future__ import annotations

from typing import Any, Generator

from api_blueprint.engine.connection import ConnectionKind, DefaultConnectionClose, MessageContract, ModelRef
from api_blueprint.engine.model import Null, create_model
from api_blueprint.engine.provider import ProviderName
from api_blueprint.engine.router import Router
from api_blueprint.engine.utils import pascal_to_snake_case, snake_to_pascal_case
from api_blueprint.engine.envelope import NoEnvelope
from api_blueprint.writer.core.contract_adapters import RouteProtocolContract, route_protocol_from_router
from api_blueprint.writer.core.contracts import RouteContract

from .common import GolangType
from .protos import GolangProto, GolangProtoAlias, GolangProtoGeneric, ensure_model


class GoRouteProtocolView:
    def __init__(
        self,
        router: Router,
        contract: RouteContract | None = None,
        protocol: RouteProtocolContract | None = None,
    ):
        self.router = router
        self.protocol = protocol or route_protocol_from_router(router, contract=contract)
        self.contract: RouteContract = self.protocol.route

    @property
    def url(self) -> str:
        return self.contract.url

    @property
    def methods(self) -> list[str]:
        return [method.upper() for method in self.router.methods]

    @property
    def root(self) -> str:
        return self.router.group.bp.root_slug

    @property
    def group(self) -> str:
        return self.router.group.branch.strip("/")

    @property
    def namespace(self) -> str:
        return self.contract.namespace

    @property
    def service_name(self) -> str:
        return self.contract.service_name

    @property
    def route_id(self) -> str:
        return self.contract.route_id

    @property
    def func_name(self) -> str:
        return self.contract.func_name

    @property
    def ctx_type(self) -> str:
        return f"CTX_{self.func_name}"

    @property
    def req_type(self) -> str:
        return f"REQ_{self.func_name}"

    @property
    def rsp_type(self) -> str:
        return f"RSP_{self.func_name}"

    @property
    def query_alias_name(self) -> str | None:
        if self.query_model is None:
            return None
        if self.is_connection:
            return f"OPEN_{self.func_name}"
        return f"{self.req_type}_QUERY"

    @property
    def body_alias_name(self) -> str | None:
        if self.protocol.request.json.model is not None:
            return f"{self.req_type}_JSON"
        if self.protocol.request.multipart.model is not None:
            return f"{self.req_type}_FORM"
        if self.protocol.request.form.model is not None:
            return f"{self.req_type}_FORM"
        if self.protocol.request.binary_schema is not None:
            return f"{{binary_package$}}{self.protocol.request.binary_schema.name}"
        return None

    @property
    def body_proto_ref(self) -> GolangProto | GolangType | None:
        if self.protocol.request.json.model is not None:
            return GolangProto.from_model_ref(ensure_model(self.protocol.request.json.model), f"{self.req_type}_JSON")
        if self.protocol.request.multipart.model is not None:
            return GolangProto.from_model_ref(ensure_model(self.protocol.request.multipart.model), f"{self.req_type}_FORM")
        if self.protocol.request.form.model is not None:
            return GolangProto.from_model_ref(ensure_model(self.protocol.request.form.model), f"{self.req_type}_FORM")
        if self.protocol.request.binary_schema is not None:
            return GolangType(f"{{binary_package$}}{self.protocol.request.binary_schema.name}")
        return None

    @property
    def local_query_type_expr(self) -> str:
        return self.query_alias_name or "any"

    @property
    def local_body_type_expr(self) -> str:
        return self.body_alias_name or "any"

    @property
    def executor_body_type_expr(self) -> str:
        if self.is_connection:
            return "any"
        return self.local_body_type_expr

    @property
    def bind_query(self) -> bool:
        return self.query_model is not None

    @property
    def bind_json(self) -> bool:
        return self.protocol.request.json.model is not None

    @property
    def bind_form(self) -> bool:
        return self.protocol.request.form.model is not None

    @property
    def bind_multipart(self) -> bool:
        return self.protocol.request.multipart.model is not None

    @property
    def bind_binary(self) -> bool:
        return self.protocol.request.binary_schema is not None

    @property
    def is_json_response(self) -> bool:
        return self.protocol.response.media_type == "application/json"

    @property
    def is_xml_response(self) -> bool:
        return self.protocol.response.media_type == "application/xml"

    @property
    def is_text_response(self) -> bool:
        return not self.is_json_response

    @property
    def response_envelope_name(self) -> str:
        return self.protocol.response.envelope.__name__

    @property
    def has_wrapped_json_response(self) -> bool:
        return self.is_json_response and self.protocol.response.envelope is not NoEnvelope

    @property
    def req_provider(self) -> str:
        options = [
            ("Q", self.query_model),
            ("F", self.protocol.request.form.model),
            ("M", self.protocol.request.multipart.model),
            ("J", self.protocol.request.json.model),
            ("B", self.protocol.request.binary_schema),
        ]
        return "".join(value for value, ok in options if ok)

    @property
    def rsp_provider(self) -> str:
        media_type_mapping = {
            "application/json": "json",
            "application/xml": "xml",
            "text/html": "html",
            "bytes": "bytes",
            "file": "file",
            "byte_stream": "byte_stream",
            "binary_schema": "binary_schema",
        }
        if self.protocol.response.kind in {"bytes", "file", "byte_stream", "binary_schema"}:
            response_type = self.protocol.response.kind
        else:
            response_type = media_type_mapping[self.protocol.response.media_type]
        return "@".join([
            response_type,
            self.protocol.response.envelope.__name__,
        ])

    @property
    def providers(self) -> str:
        provider_specs: list[str] = []
        providers = self.router.providers
        if not providers:
            providers = [
                ProviderName.REQ,
                ProviderName.HANDLE,
                ProviderName.RSP,
            ]
        for provider in providers:
            if isinstance(provider, ProviderName):
                provider_name = provider.value
                provider_data = None
            else:
                provider_name = provider.name
                provider_data = provider.data
            if self.is_connection and provider_name in {
                ProviderName.HANDLE.value,
                ProviderName.RSP.value,
            }:
                continue
            data = provider_data
            if provider_name == ProviderName.REQ.value:
                data = self.req_provider
            elif provider_name == ProviderName.RSP.value:
                data = self.rsp_provider
            key = provider_name
            if data:
                key += f"={data}"
            provider_specs.append(key)
        return "|".join(provider_specs)

    @property
    def http_raw_response(self) -> bool:
        return bool(self.router.extra.get("http_raw_response"))

    def protos(self) -> Generator[GolangProto, None, None]:
        req_query_proto = None
        req_form_proto = None
        req_json_proto = None
        req_body_proto: GolangProto | GolangType | None = None

        if self.query_model is not None:
            req_query_proto = GolangProto.from_model_ref(ensure_model(self.query_model), self.query_alias_name)
            yield req_query_proto
        if self.protocol.request.form.model is not None:
            req_form_proto = GolangProto.from_model_ref(
                ensure_model(self.protocol.request.form.model),
                f"{self.req_type}_FORM",
            )
            yield req_form_proto
            req_body_proto = req_form_proto
        if self.protocol.request.multipart.model is not None:
            req_form_proto = GolangProto.from_model_ref(
                ensure_model(self.protocol.request.multipart.model),
                f"{self.req_type}_FORM",
            )
            yield req_form_proto
            req_body_proto = req_form_proto
        if self.protocol.request.json.model is not None:
            req_json_proto = GolangProto.from_model_ref(
                ensure_model(self.protocol.request.json.model),
                f"{self.req_type}_JSON",
            )
            yield req_json_proto
            req_body_proto = req_json_proto
        if self.protocol.request.binary_schema is not None:
            req_body_proto = GolangType(f"{{binary_package$}}{self.protocol.request.binary_schema.name}")

        yield GolangProto(
            self.req_type,
            create_model(
                self.req_type,
                {
                    "Q": self.query_model,
                    "B": self.protocol.request.json.model or self.protocol.request.multipart.model or self.protocol.request.form.model or Null(),
                },
            ),
            "generic",
            generic=GolangProtoGeneric(
                name=GolangType("{provider_package$}REQ"),
                types=[req_query_proto or GolangType("any"), req_body_proto or GolangType("any")],
            ),
        )

        rsp_json_proto = None
        rsp_body_ref: GolangProto | GolangType | None = None
        if self.protocol.response.model.model is not None:
            rsp_json_proto = GolangProto.from_model_ref(
                ensure_model(self.protocol.response.model.model),
                f"{self.rsp_type}_BODY",
            )
            yield rsp_json_proto
            rsp_body_ref = rsp_json_proto
        elif self.protocol.response.kind in {"bytes", "file", "byte_stream"}:
            rsp_body_ref = GolangType("{provider_package$}RawResponse")
        elif self.protocol.response.binary_schema is not None:
            rsp_body_ref = GolangType(f"{{binary_package$}}{self.protocol.response.binary_schema.name}")

        yield GolangProto(
            self.rsp_type,
            self.protocol.response.model.model,
            "alias",
            alias=GolangProtoAlias(
                name=GolangType(rsp_body_ref.name if isinstance(rsp_body_ref, GolangProto) else str(rsp_body_ref or "any")),
                proto=rsp_json_proto,
            ),
        )

        yield GolangProto(
            self.ctx_type,
            create_model(
                self.req_type,
                {
                    "Q": self.query_model or Null(),
                    "B": self.protocol.request.json.model or self.protocol.request.multipart.model or self.protocol.request.form.model or Null(),
                    "P": self.protocol.response.model.model or Null(),
                },
            ),
            "generic",
            generic=GolangProtoGeneric(
                name=GolangType("{provider_package$}Context"),
                types=[
                    req_query_proto or GolangType("any"),
                    req_body_proto or GolangType("any"),
                    rsp_body_ref or GolangType("any"),
                ],
            ),
        )

        yield from self.message_protos()

    def com_protos(self) -> Generator[GolangProto, None, None]:
        if self.query_model is not None:
            yield from GolangProto.from_model(self.query_model).com_protos()
        if self.protocol.request.form.model is not None:
            yield from GolangProto.from_model(self.protocol.request.form.model).com_protos()
        if self.protocol.request.multipart.model is not None:
            yield from GolangProto.from_model(self.protocol.request.multipart.model).com_protos()
        if self.protocol.request.json.model is not None:
            yield from GolangProto.from_model(self.protocol.request.json.model).com_protos()
        if self.protocol.response.model.model is not None:
            yield from GolangProto.from_model(self.protocol.response.model.model).com_protos()
        for recv in self.protocol.recvs:
            yield from GolangProto.from_model(recv).com_protos()
        for send in self.protocol.sends:
            yield from GolangProto.from_model(send).com_protos()
        for model in self.connection_message_models():
            yield from GolangProto.from_model(model).com_protos()
        if self.is_connection:
            yield from GolangProto.from_model(self.effective_close_model).com_protos()

    @property
    def connection_kind(self) -> ConnectionKind:
        return self.router.connection_kind

    @property
    def is_stream(self) -> bool:
        return self.connection_kind == ConnectionKind.STREAM

    @property
    def is_channel(self) -> bool:
        return self.connection_kind == ConnectionKind.CHANNEL

    @property
    def is_connection(self) -> bool:
        return self.is_stream or self.is_channel

    @property
    def query_model(self) -> ModelRef | None:
        if self.is_connection:
            return self.protocol.request.open.model
        return self.protocol.request.query.model

    @property
    def server_message_type(self) -> str:
        return self._message_type_name(self.protocol.server_message, "SERVER")

    @property
    def client_message_type(self) -> str:
        return self._message_type_name(self.protocol.client_message, "CLIENT")

    @property
    def effective_close_model(self) -> ModelRef:
        return self.protocol.close_model or DefaultConnectionClose

    @property
    def close_message_type(self) -> str:
        if not self.is_connection:
            return "any"
        return f"CLOSE_{self.func_name}"

    @property
    def stream_signature(self) -> str:
        return (
            f"{self.func_name}(\n"
            f"\tctx *{self.ctx_type},\n"
            f"\tstream STREAM_{self.func_name},\n"
            ") error"
        )

    @property
    def channel_signature(self) -> str:
        return (
            f"{self.func_name}(\n"
            f"\tctx *{self.ctx_type},\n"
            f"\tchannel CHANNEL_{self.func_name},\n"
            ") error"
        )

    @property
    def rpc_signature(self) -> str:
        return f"{self.func_name}(ctx *{self.ctx_type}, req *{self.req_type})(rsp *{self.rsp_type}, err error)"

    @property
    def interface_signature(self) -> str:
        if self.is_stream:
            return self.stream_signature
        if self.is_channel:
            return self.channel_signature
        return self.rpc_signature

    @property
    def default_body(self) -> str:
        if self.is_connection:
            return 'return fmt.Errorf("not implemented")'
        return 'return nil, fmt.Errorf("not implemented")'

    def message_protos(self) -> Generator[GolangProto, None, None]:
        yield from self._message_contract_protos(self.protocol.server_message, "SERVER")
        yield from self._message_contract_protos(self.protocol.client_message, "CLIENT")
        if self.is_connection:
            yield GolangProto.from_model_ref(ensure_model(self.effective_close_model), self.close_message_type)

    def connection_message_models(self) -> Generator[ModelRef, None, None]:
        for contract in (self.protocol.server_message, self.protocol.client_message):
            if contract is None:
                continue
            for variant in contract.variants:
                yield variant.model

    def message_unions(self) -> list[dict[str, Any]]:
        unions: list[dict[str, Any]] = []
        for contract in (self.protocol.server_message, self.protocol.client_message):
            if contract is None or not contract.is_union or contract.name is None:
                continue
            unions.append(self._message_union(contract))
        return unions

    def connection_alias(self) -> dict[str, str] | None:
        if self.is_stream:
            return {
                "name": f"STREAM_{self.func_name}",
                "kind": "stream",
                "open_type": self.local_query_type_expr,
                "server_message_type": self.server_message_type,
                "close_type": self.close_message_type,
            }
        if self.is_channel:
            return {
                "name": f"CHANNEL_{self.func_name}",
                "kind": "channel",
                "open_type": self.local_query_type_expr,
                "server_message_type": self.server_message_type,
                "client_message_type": self.client_message_type,
                "close_type": self.close_message_type,
            }
        return None

    def client_message_cases(self) -> dict[str, Any] | None:
        contract = self._named_union(self.protocol.client_message)
        if contract is None:
            return None
        return {
            "name": contract.name,
            "case_interface": f"{contract.name}Case",
            "processor_type": f"{contract.name}Processor",
            "visitor": f"Visit{contract.name}",
            "error_type": f"{contract.name}Error",
            "error_kind_type": f"{contract.name}ErrorKind",
            "new_error": f"new{contract.name}Error",
            "wrap_error": f"wrap{contract.name}HandlerError",
            "variants": self._case_variants(contract),
        }

    def connection_scaffold(self) -> dict[str, Any] | None:
        if not self.is_channel:
            return None
        cases = self.client_message_cases()
        if cases is None:
            return None
        base_name = pascal_to_snake_case(self.func_name)
        lower_name = self._lower_camel(self.func_name)
        route_label = base_name.replace("_", " ")
        return {
            "base_name": base_name,
            "session_file": f"{base_name}_session.go",
            "processor_file": f"{base_name}_processor.go",
            "error_file": f"{base_name}_error.go",
            "func_name": self.func_name,
            "route_label": route_label,
            "ctx_type": self.ctx_type,
            "channel_alias": f"CHANNEL_{self.func_name}",
            "client_message_type": self.client_message_type,
            "session_type": f"{lower_name}RouteSession",
            "new_session": f"new{self.func_name}RouteSession",
            "scope_type": f"{lower_name}MessageScope",
            "processor_struct": f"{lower_name}MessageProcessor",
            "processor_interface": cases["processor_type"],
            "visitor": cases["visitor"],
            "error_type": cases["error_type"],
            "error_kind_type": cases["error_kind_type"],
            "as_error": f"As{cases['name']}Error",
            "is_error_kind": f"Is{cases['name']}ErrorKind",
            "error_kinds": {
                "nil_message": f"{cases['error_type']}NilMessage",
                "nil_processor": f"{cases['error_type']}NilProcessor",
                "unknown_type": f"{cases['error_type']}UnknownType",
                "decode_failed": f"{cases['error_type']}DecodeFailed",
                "handler_failed": f"{cases['error_type']}HandlerFailed",
            },
            "variants": [
                {
                    **variant,
                    "message_label": f"{route_label} {pascal_to_snake_case(variant['name']).replace('_', ' ')}",
                }
                for variant in cases["variants"]
            ],
        }

    def _named_union(self, contract: MessageContract | None) -> MessageContract | None:
        if contract is None or not contract.is_union or contract.name is None:
            return None
        return contract

    def _message_union(self, contract: MessageContract) -> dict[str, Any]:
        return {
            "name": contract.name,
            "variants": self._message_variants(contract),
        }

    def _message_variants(self, contract: MessageContract) -> list[dict[str, Any]]:
        variants = []
        for variant in contract.variants:
            variant_name = snake_to_pascal_case(variant.key)
            variants.append(
                {
                    "key": variant.key,
                    "name": variant_name,
                    "const": f"{contract.name}Type{variant_name}",
                    "ctor": f"New{contract.name}{variant_name}",
                    "decode": f"Decode{variant_name}",
                    "data_type": self._variant_alias_name(contract, variant.key),
                }
            )
        return variants

    def _case_variants(self, contract: MessageContract) -> list[dict[str, Any]]:
        return [
            {
                **variant,
                "case_type": f"{contract.name}{variant['name']}Case",
                "handler": f"On{variant['name']}",
            }
            for variant in self._message_variants(contract)
        ]

    @staticmethod
    def _lower_camel(name: str) -> str:
        if not name:
            return name
        return name[:1].lower() + name[1:]

    def _message_contract_protos(
        self,
        contract: MessageContract | None,
        direction: str,
    ) -> Generator[GolangProto, None, None]:
        if contract is None:
            return
        if contract.single_model is not None:
            yield GolangProto.from_model_ref(ensure_model(contract.single_model), self._message_type_name(contract, direction))
            return
        for variant in contract.variants:
            yield GolangProto.from_model_ref(
                ensure_model(variant.model),
                self._variant_alias_name(contract, variant.key),
            )

    def _message_type_name(self, contract: MessageContract | None, direction: str) -> str:
        if contract is None:
            return "any"
        if contract.is_union and contract.name is not None:
            return contract.name
        return f"{direction}_{self.func_name}_MESSAGE"

    @staticmethod
    def _variant_alias_name(contract: MessageContract, key: str) -> str:
        return f"{contract.name}_{snake_to_pascal_case(key)}_DATA"

    @staticmethod
    def shared_type_expr(type_name: str) -> str:
        if type_name == "any":
            return "any"
        return f"shared.{type_name}"


GolangRouter = GoRouteProtocolView


__all__ = ("GoRouteProtocolView", "GolangRouter")
