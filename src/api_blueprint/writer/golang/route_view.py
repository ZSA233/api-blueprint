from __future__ import annotations

from typing import Any, Generator

from api_blueprint.engine.connection import ConnectionKind, DefaultConnectionClose, MessageContract, ModelRef
from api_blueprint.engine.model import Null, create_model
from api_blueprint.engine.provider import ProviderName
from api_blueprint.engine.router import Router
from api_blueprint.engine.utils import snake_to_pascal_case
from api_blueprint.engine.wrapper import NoneWrapper
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
        return self.router.group.bp.root.strip("/") or "root"

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
        if self.protocol.request.form.model is not None:
            return f"{self.req_type}_FORM"
        if self.protocol.request.binary_schema is not None:
            return f"{{binary_package$}}{self.protocol.request.binary_schema.name}"
        return None

    @property
    def body_proto_ref(self) -> GolangProto | GolangType | None:
        if self.protocol.request.json.model is not None:
            return GolangProto.from_model_ref(ensure_model(self.protocol.request.json.model), f"{self.req_type}_JSON")
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
        if "WS" in self.methods or self.is_connection:
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
    def response_wrapper_name(self) -> str:
        return self.protocol.response.wrapper.__name__

    @property
    def has_wrapped_json_response(self) -> bool:
        return self.is_json_response and self.protocol.response.wrapper is not NoneWrapper

    @property
    def req_provider(self) -> str:
        options = [
            ("Q", self.query_model),
            ("F", self.protocol.request.form.model),
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
        }
        return "@".join([
            media_type_mapping[self.protocol.response.media_type],
            self.protocol.response.wrapper.__name__,
        ])

    @property
    def providers(self) -> str:
        provider_specs: list[str] = []
        for provider in self.router.providers:
            if self.is_connection and provider.name in {
                ProviderName.HANDLE.value,
                ProviderName.RSP.value,
                ProviderName.WS_HANDLE.value,
            }:
                continue
            data = provider.data
            if provider.name == ProviderName.REQ.value:
                data = self.req_provider
            elif provider.name == ProviderName.RSP.value:
                data = self.rsp_provider
            elif provider.name == ProviderName.WS_HANDLE.value:
                data = ",".join(data)

            key = provider.name
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
                    "B": self.protocol.request.json.model or self.protocol.request.form.model or Null(),
                },
            ),
            "generic",
            generic=GolangProtoGeneric(
                name=GolangType("{provider_package$}REQ"),
                types=[req_query_proto or GolangType("any"), req_body_proto or GolangType("any")],
            ),
        )

        rsp_json_proto = None
        if self.protocol.response.model.model is not None:
            rsp_json_proto = GolangProto.from_model_ref(
                ensure_model(self.protocol.response.model.model),
                f"{self.rsp_type}_BODY",
            )
            yield rsp_json_proto

        yield GolangProto(
            self.rsp_type,
            self.protocol.response.model.model,
            "alias",
            alias=GolangProtoAlias(
                name=GolangType(rsp_json_proto.name if rsp_json_proto else "any"),
                proto=rsp_json_proto,
            ),
        )

        yield GolangProto(
            self.ctx_type,
            create_model(
                self.req_type,
                {
                    "Q": self.query_model or Null(),
                    "B": self.protocol.request.json.model or self.protocol.request.form.model or Null(),
                    "P": self.protocol.response.model.model or Null(),
                },
            ),
            "generic",
            generic=GolangProtoGeneric(
                name=GolangType("{provider_package$}Context"),
                types=[
                    req_query_proto or GolangType("any"),
                    req_body_proto or GolangType("any"),
                    rsp_json_proto or GolangType("any"),
                ],
            ),
        )

        yield from self.message_protos()

    def com_protos(self) -> Generator[GolangProto, None, None]:
        if self.query_model is not None:
            yield from GolangProto.from_model(self.query_model).com_protos()
        if self.protocol.request.form.model is not None:
            yield from GolangProto.from_model(self.protocol.request.form.model).com_protos()
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
            f"\tstream providers.Stream[{self.local_query_type_expr}, {self.server_message_type}, {self.close_message_type}],\n"
            ") error"
        )

    @property
    def channel_signature(self) -> str:
        return (
            f"{self.func_name}(\n"
            f"\tctx *{self.ctx_type},\n"
            f"\tchannel providers.Channel[{self.local_query_type_expr}, {self.server_message_type}, {self.client_message_type}, {self.close_message_type}],\n"
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
            if contract is None or not contract.is_union:
                continue
            variants = []
            for variant in contract.variants:
                data_type = self._variant_alias_name(contract, variant.key)
                variants.append(
                    {
                        "key": variant.key,
                        "const": f"{contract.name}Type{snake_to_pascal_case(variant.key)}",
                        "ctor": f"New{contract.name}{snake_to_pascal_case(variant.key)}",
                        "decode": f"Decode{snake_to_pascal_case(variant.key)}",
                        "data_type": data_type,
                    }
                )
            unions.append({"name": contract.name, "variants": variants})
        return unions

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
