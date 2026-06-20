from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
import json

from api_blueprint.writer.java.blueprint import JavaApiGroup, JavaRoute
from api_blueprint.writer.java.planner import JavaBlueprintPlan, JavaRouteGroupPlan
from api_blueprint.writer.java.writer import JAVA_SERVER_GENERATED_HEADER, JavaBaseWriter


@dataclass(frozen=True)
class JavaSpringPolicyMapping:
    provider: str
    annotation: str
    args: str | None = None
    imports: tuple[str, ...] = ()


class JavaServerWriter(JavaBaseWriter):
    target_label = "java-server"
    server_mode = True
    generated_header = JAVA_SERVER_GENERATED_HEADER

    def __init__(
        self,
        working_dir: str | Path = ".",
        *,
        package: str,
        base_url: str | None = None,
        base_url_expr: str | None = None,
        include: Sequence[str] = (),
        exclude: Sequence[str] = (),
        allow_empty: bool = False,
        contract_graph=None,
        spring_contract_mode: str = "strict",
        spring_policy_mappings: Sequence[object] = (),
        spring_public_paths: Sequence[str] = (),
        spring_exclude_server_paths: Sequence[str] = (),
    ) -> None:
        super().__init__(
            working_dir,
            package=package,
            base_url=base_url,
            base_url_expr=base_url_expr,
            include=include,
            exclude=exclude,
            allow_empty=allow_empty,
            contract_graph=contract_graph,
        )
        self.spring_contract_mode = spring_contract_mode
        self.spring_policy_mappings = tuple(_coerce_policy_mapping(mapping) for mapping in spring_policy_mappings)
        self._spring_policy_mappings_by_provider = self._policy_mappings_by_provider()
        self.spring_public_paths = tuple(spring_public_paths)
        self.spring_exclude_server_paths = tuple(spring_exclude_server_paths)
        if self.spring_contract_mode not in {"audit", "public", "strict"}:
            raise ValueError(
                "[java-server] spring_contract_mode must be one of audit, public, strict; "
                f"got {self.spring_contract_mode!r}"
            )
        if not self.spring_public_paths:
            raise ValueError("[java-server] spring_public_paths is required for generated Spring controllers")

    def _gen_blueprint(
        self,
        bp: Any,
        schemas: Mapping[str, dict[str, Any]],
        errors: tuple[Any, ...],
        route_errors: dict[str, tuple[Any, ...]],
    ) -> None:
        self._validate_supported_routes(bp)
        super()._gen_blueprint(bp, schemas, errors, route_errors)

    def _validate_supported_routes(self, bp: Any) -> None:
        unsupported = [route for route in bp.routes if not route.is_rpc]
        if not unsupported:
            return
        rendered = ", ".join(f"{route.route_id} ({route.kind.upper()} {route.url})" for route in unsupported)
        raise ValueError(
            "[java-server] controller-delegate generation only supports RPC routes; "
            f"exclude STREAM/CHANNEL routes from java-server target: {rendered}"
        )

    def _write_server_runtime(self, plan: JavaBlueprintPlan, context: dict[str, object]) -> None:
        for stale_name in (
            "ApiServerChannel.java",
            "ApiServerContext.java",
            "ApiServerResponse.java",
            "ApiServerStream.java",
            "GenApiServerChannel.java",
            "GenApiServerContext.java",
            "GenApiServerResponse.java",
            "GenApiServerStream.java",
        ):
            self._unlink_generated_file(plan.runtime.directory / stale_name)

    def _write_server_transport(self, plan: JavaBlueprintPlan, context: dict[str, object]) -> None:
        for stale_name in ("GenSpringApiConfiguration.java", "GenSpringServerConfig.java"):
            self._unlink_generated_file(plan.http_transport.directory / stale_name)
        bp = context["bp"]
        for group in bp.groups.values():  # type: ignore[union-attr]
            self._unlink_generated_file(plan.http_transport.directory / group.package_path / f"{group.controller_class}.java")
        self._write_generated(
            plan.root_directory / "annotations" / "ApiBlueprintOperation.java",
            "ApiBlueprintOperation.java",
            context,
            "server/annotations",
        )
        self._write_generated(
            plan.root_directory / "spring" / "GenSpringMvcContractAssertions.java",
            "GenSpringMvcContractAssertions.java",
            context,
            "server/spring",
        )
        for output_name, template_path in (
            ("GenSpringRequestContext.java", "GenSpringRequestContext.java"),
            ("GenSpringRequestBinder.java", "GenSpringRequestBinder.java"),
            ("GenSpringResponseWriter.java", "GenSpringResponseWriter.java"),
        ):
            self._write_generated(
                plan.root_directory / "spring" / output_name,
                template_path,
                context,
                "server/spring",
            )

    def _write_group_models(self, group_plan: JavaRouteGroupPlan, context: dict[str, object]) -> None:
        group = group_plan.group
        bp = context["bp"]
        for stale_name in (
            f"{group.types_class}.java",
            f"{group.generated_service_class}.java",
            f"{group.stub_class}.java",
            f"{group.service_class}Stub.java",
        ):
            self._unlink_generated_file(group_plan.directory / stale_name)
        self._unlink_generated_file(self.root_dir(bp) / "types" / group.package_path / f"{group.types_class}.java")  # type: ignore[arg-type]
        types_dir = self.route_group_directory(bp, group) / "types"
        self._write_generated(
            types_dir / f"{group.types_class}.java",
            "GenApiGroupTypes.java",
            {**context, "group": group},
            "server/types",
        )

    def _write_server_group(self, group_plan: JavaRouteGroupPlan, context: dict[str, object]) -> None:
        group = group_plan.group
        bp = context["bp"]
        for stale_name in (
            f"{group.generated_service_class}.java",
            f"{group.stub_class}.java",
            f"{group.service_class}Stub.java",
        ):
            self._unlink_generated_file(group_plan.directory / stale_name)
        annotations_dir = self.route_group_directory(bp, group) / "annotations"
        controllers_dir = self.route_group_directory(bp, group) / "controllers"
        delegates_dir = self.route_group_directory(bp, group) / "delegates"
        adapters_dir = self.route_group_directory(bp, group) / "adapters"
        if annotations_dir.exists():
            for generated_annotation in annotations_dir.glob("*.java"):
                self._unlink_generated_file(generated_annotation)
        for route in group.routes:
            self._unlink_generated_file(
                self.root_dir(bp)  # type: ignore[arg-type]
                / "annotations"
                / group.package_path
                / f"{self.route_annotation_name(route, group)}.java"
            )
        self._write_generated(
            controllers_dir / f"{group.controller_class}.java",
            "GenApiGroupController.java",
            {**context, "group": group},
            "server/controllers",
        )
        self._write_generated(
            delegates_dir / f"{group.delegate_class}.java",
            "GenApiGroupDelegate.java",
            {**context, "group": group},
            "server/delegates",
        )
        self._unlink_generated_file(
            self.root_dir(bp)  # type: ignore[arg-type]
            / "adapters"
            / group.package_path
            / f"{self.group_adapters_class(group)}.java"
        )
        self._write_generated(
            adapters_dir / f"{self.group_adapters_class(group)}.java",
            "GenApiGroupAdapters.java",
            {**context, "group": group},
            "server/adapters",
        )

    def _policy_mappings_by_provider(self) -> dict[str, JavaSpringPolicyMapping]:
        mappings: dict[str, JavaSpringPolicyMapping] = {}
        duplicates: list[str] = []
        for mapping in self.spring_policy_mappings:
            if not mapping.provider:
                raise ValueError("[java-server] spring policy mapping provider is required")
            if not mapping.annotation:
                raise ValueError(f"[java-server] spring policy mapping annotation is required: {mapping.provider}")
            if mapping.provider in mappings:
                duplicates.append(mapping.provider)
            mappings[mapping.provider] = mapping
        if duplicates:
            rendered = ", ".join(sorted(set(duplicates)))
            raise ValueError(f"[java-server] duplicate spring policy mapping provider(s): {rendered}")
        return mappings

    def spring_policy_mappings_for_route(self, route: JavaRoute) -> tuple[JavaSpringPolicyMapping, ...]:
        providers = route.route.get("providers")
        if not isinstance(providers, list):
            return ()
        mappings: list[JavaSpringPolicyMapping] = []
        seen: set[str] = set()
        for provider in providers:
            if isinstance(provider, Mapping):
                provider_name = str(provider.get("name") or "")
            else:
                provider_name = str(provider)
            mapping = self._spring_policy_mappings_by_provider.get(provider_name)
            if mapping is None or mapping.provider in seen:
                continue
            mappings.append(mapping)
            seen.add(mapping.provider)
        return tuple(mappings)

    def policies_for_route(
        self,
        route: JavaRoute,
        group: JavaApiGroup | None = None,
    ) -> tuple[JavaSpringPolicyMapping, ...]:
        return self.spring_policy_mappings_for_route(route)

    def spring_route_imports(self, route: JavaRoute, group: JavaApiGroup | None = None) -> tuple[str, ...]:
        imports: list[str] = []
        for import_name in self.spring_mapping_imports(route):
            imports.append(import_name)
        for policy in self.policies_for_route(route, group):
            imports.append(policy.annotation)
            imports.extend(policy.imports)
        return tuple(sorted(dict.fromkeys(imports)))

    def spring_route_import_block(self, route: JavaRoute, group: JavaApiGroup | None = None) -> str:
        return "\n".join(f"import {import_name};" for import_name in self.spring_route_imports(route, group))

    def java_import_block(self, imports: Sequence[str]) -> str:
        return "\n".join(f"import {import_name};" for import_name in imports)

    def server_controller_imports(self, bp: Any, group: JavaApiGroup) -> tuple[str, ...]:
        has_path_routes = any(route.path_model is not None for route in group.routes)
        imports = [
            f"{bp.root_package}.annotations.ApiBlueprintOperation",
            f"{bp.root_package}.runtime.GenApiRawResponse",
            f"{bp.root_package}.runtime.GenApiResponseEnvelope",
            f"{bp.root_package}.runtime.GenApiStreamResponse",
            f"{bp.root_package}.spring.GenSpringRequestBinder",
            f"{bp.root_package}.spring.GenSpringRequestContext",
            f"{bp.root_package}.spring.GenSpringResponseWriter",
            f"{self.group_delegates_package(bp, group)}.{group.delegate_class}",
            f"{self.group_types_package(bp, group)}.{group.types_class}",
            "jakarta.servlet.http.HttpServletRequest",
            "org.springframework.http.ResponseEntity",
            "org.springframework.web.bind.annotation.ModelAttribute",
            "org.springframework.web.bind.annotation.RequestBody",
            "org.springframework.web.bind.annotation.RestController",
            "org.springframework.web.multipart.MultipartHttpServletRequest",
        ]
        if has_path_routes:
            imports.extend(
                [
                    "java.util.Map",
                    "org.springframework.web.bind.annotation.PathVariable",
                ]
            )
        if group.runtime_types_ref == "GenApiTypes":
            imports.append(f"{bp.root_package}.runtime.GenApiTypes")
        for route in group.routes:
            imports.extend(self.spring_route_imports(route, group))
        return tuple(sorted(dict.fromkeys(imports)))

    def server_delegate_imports(self, bp: Any, group: JavaApiGroup) -> tuple[str, ...]:
        imports = [
            f"{bp.root_package}.runtime.GenApiRawResponse",
            f"{bp.root_package}.runtime.GenApiStreamResponse",
            f"{bp.root_package}.spring.GenSpringRequestContext",
            f"{self.group_types_package(bp, group)}.{group.types_class}",
        ]
        if group.runtime_types_ref == "GenApiTypes":
            imports.append(f"{bp.root_package}.runtime.GenApiTypes")
        return tuple(sorted(dict.fromkeys(imports)))

    def policy_annotation_exprs_for_route(
        self,
        route: JavaRoute,
        group: JavaApiGroup | None = None,
    ) -> tuple[str, ...]:
        return tuple(self.policy_annotation_expr(policy) for policy in self.policies_for_route(route, group))

    def route_annotation_name(self, route: JavaRoute, group: JavaApiGroup | None = None) -> str:
        return f"Gen{route.operation_type_name}"

    def route_group_directory(self, bp: Any, group: JavaApiGroup) -> Path:
        return self.root_dir(bp) / "routes" / group.package_path

    def route_group_package(self, bp: Any, group: JavaApiGroup) -> str:
        return f"{bp.root_package}.routes.{group.package_suffix}"

    def group_controllers_package(self, bp: Any, group: JavaApiGroup) -> str:
        return f"{self.route_group_package(bp, group)}.controllers"

    def group_controller_class(self, bp: Any, group: JavaApiGroup) -> str:
        return f"{self.group_controllers_package(bp, group)}.{group.controller_class}"

    def group_delegates_package(self, bp: Any, group: JavaApiGroup) -> str:
        return f"{self.route_group_package(bp, group)}.delegates"

    def group_delegate_class(self, bp: Any, group: JavaApiGroup) -> str:
        return f"{self.group_delegates_package(bp, group)}.{group.delegate_class}"

    def group_types_package(self, bp: Any, group: JavaApiGroup) -> str:
        return f"{self.route_group_package(bp, group)}.types"

    def group_types_ref(self, bp: Any, group: JavaApiGroup) -> str:
        return f"{self.group_types_package(bp, group)}.{group.types_class}"

    def group_adapters_package(self, bp: Any, group: JavaApiGroup) -> str:
        return f"{self.route_group_package(bp, group)}.adapters"

    def group_adapters_class(self, group: JavaApiGroup) -> str:
        return f"Gen{group.class_name.removesuffix('Api')}Adapters"

    def spring_mapping_annotation(self, route: JavaRoute) -> str:
        if not route.methods:
            return f"@RequestMapping(path = {self.java_string(route.url)})"
        methods = ", ".join(f"RequestMethod.{method}" for method in route.methods)
        return f"@RequestMapping(path = {self.java_string(route.url)}, method = {{{methods}}})"

    def spring_mapping_imports(self, route: JavaRoute) -> tuple[str, ...]:
        if not route.methods:
            return ("org.springframework.web.bind.annotation.RequestMapping",)
        return (
            "org.springframework.web.bind.annotation.RequestMapping",
            "org.springframework.web.bind.annotation.RequestMethod",
        )

    def java_simple_name(self, qualified_name: str) -> str:
        return qualified_name.rsplit(".", 1)[-1]

    def java_string(self, value: object) -> str:
        return json.dumps(str(value), ensure_ascii=False)

    def policy_annotation_expr(self, policy: JavaSpringPolicyMapping) -> str:
        name = self.java_simple_name(policy.annotation)
        if policy.args:
            return f"@{name}({policy.args})"
        return f"@{name}"

    def route_request_types(self, route: JavaRoute, group: JavaApiGroup) -> tuple[str, ...]:
        types: list[str] = []
        for schema_name in (
            route.query_model,
            route.json_model,
            route.form_model,
            route.multipart_model,
            route.binary_model,
            route.open_model,
        ):
            if schema_name:
                types.append(self.schema_type(schema_name, group))
        if route.binary_schema_type:
            types.append(f"{group.types_class}.{route.binary_schema_type}")
        return tuple(types)

    def route_response_type(self, route: JavaRoute, group: JavaApiGroup) -> str:
        return self.response_type(route, group)

    def route_contract_request_type_names(self, bp: Any, route: JavaRoute, group: JavaApiGroup) -> tuple[str, ...]:
        return tuple(self._server_contract_type_name(bp, group, type_name) for type_name in self.route_request_types(route, group))

    def route_contract_response_type_name(self, bp: Any, route: JavaRoute, group: JavaApiGroup) -> str:
        response_type = self.route_response_type(route, group)
        if response_type in {"void", "Object", "String", "byte[]"}:
            return ""
        if response_type in {"GenApiRawResponse", "GenApiStreamResponse"}:
            return f"{bp.root_package}.runtime.{response_type}"
        return self._server_contract_type_name(bp, group, response_type)

    def route_required_request_fields(self, route: JavaRoute, group: JavaApiGroup) -> tuple[str, ...]:
        fields: list[str] = []
        for schema_name in (route.query_model, route.json_model, route.form_model, route.multipart_model):
            if not schema_name:
                continue
            schema = self.catalog.schema(schema_name, owner_group=group)
            fields.extend(field.wire_name for field in schema.fields if not field.optional)
        return tuple(dict.fromkeys(fields))

    def route_request_binding(self, route: JavaRoute) -> str:
        return "generated"

    def route_response_binding(self, route: JavaRoute) -> str:
        return "generated"

    def spring_contract_runtime_mode(self) -> str:
        return {
            "audit": "AUDIT",
            "public": "PUBLIC",
            "strict": "STRICT",
        }.get(self.spring_contract_mode, "STRICT")

    def controller_method_parameters(self, route: JavaRoute, group: JavaApiGroup) -> tuple[str, ...]:
        params: list[str] = []
        if route.path_model:
            params.append("@PathVariable Map<String, String> pathVariables")
        if route.query_model:
            params.append(f"@ModelAttribute {self.schema_type(route.query_model, group)} query")
        if route.json_model:
            params.append(f"@RequestBody {self.schema_type(route.json_model, group)} json")
        if route.form_model:
            params.append(f"@ModelAttribute {self.schema_type(route.form_model, group)} form")
        if route.multipart_model:
            params.append("MultipartHttpServletRequest multipartRequest")
        if route.binary_schema is not None or route.binary_model:
            params.append("@RequestBody byte[] binaryBody")
        params.append("HttpServletRequest servletRequest")
        return tuple(params)

    def controller_pre_delegate_lines(self, route: JavaRoute, group: JavaApiGroup) -> tuple[str, ...]:
        lines: list[str] = []
        if route.path_model:
            path_type = self.schema_type(route.path_model, group)
            lines.append(
                f"{path_type} path;"
            )
            lines.append("try {")
            lines.append(
                f"    path = GenSpringRequestBinder.bindPath(pathVariables, {path_type}.class);"
            )
            lines.append("} catch (IllegalArgumentException error) {")
            lines.append("    return ResponseEntity.badRequest().build();")
            lines.append("}")
        if route.multipart_model:
            lines.append(
                f"{self.schema_type(route.multipart_model, group)} multipart = "
                f"GenSpringRequestBinder.bindMultipart(multipartRequest, "
                f"{self.schema_type(route.multipart_model, group)}.class);"
            )
        if route.binary_schema is not None and route.binary_schema_type:
            lines.append(f"{group.types_class}.{route.binary_schema_type} binary = {group.types_class}.{route.binary_schema_type}Wire.parse(binaryBody);")
        elif route.binary_model:
            lines.append("byte[] binary = binaryBody == null ? new byte[0] : binaryBody.clone();")
        return tuple(lines)

    def delegate_method_parameters(self, route: JavaRoute, group: JavaApiGroup) -> tuple[str, ...]:
        params = [f"{type_name} {name}" for type_name, name in self.route_params(route, group)]
        params.append("GenSpringRequestContext context")
        return tuple(params)

    def delegate_call_arguments(self, route: JavaRoute, group: JavaApiGroup) -> tuple[str, ...]:
        args = [name for _type_name, name in self.route_params(route, group)]
        args.append("GenSpringRequestContext.of(servletRequest)")
        return tuple(args)

    def controller_return_statement(self, route: JavaRoute, group: JavaApiGroup, value_name: str) -> str:
        if route.is_binary_schema_response and route.response_binary_schema_type:
            return (
                "return GenSpringResponseWriter.binary("
                f"{group.types_class}.{route.response_binary_schema_type}Wire.toBinaryBody({value_name})"
                ");"
            )
        return (
            "return GenSpringResponseWriter.response("
            f"{value_name}, {route.response_envelope_literal}, {self.java_string(route.response_media_type)}, "
            f"{self.java_string(route.response_kind)}"
            ");"
        )

    def controller_void_return_statement(self, route: JavaRoute, group: JavaApiGroup) -> str:
        return (
            "return GenSpringResponseWriter.response("
            f"null, {route.response_envelope_literal}, {self.java_string(route.response_media_type)}, "
            f"{self.java_string(route.response_kind)}"
            ");"
        )

    def _server_contract_type_name(self, bp: Any, group: JavaApiGroup, type_name: str) -> str:
        if type_name.startswith(f"{group.types_class}."):
            return f"{self.group_types_ref(bp, group)}.{type_name.split('.', 1)[1]}"
        if type_name.startswith("GenApiTypes."):
            return f"{bp.root_package}.runtime.{type_name}"
        return type_name


def _coerce_policy_mapping(value: object) -> JavaSpringPolicyMapping:
    if isinstance(value, JavaSpringPolicyMapping):
        return value
    if isinstance(value, Mapping):
        return JavaSpringPolicyMapping(
            provider=str(value.get("provider") or ""),
            annotation=str(value.get("annotation") or ""),
            args=str(value["args"]) if value.get("args") is not None else None,
            imports=tuple(str(item) for item in value.get("imports", ()) or ()),
        )
    return JavaSpringPolicyMapping(
        provider=str(getattr(value, "provider")),
        annotation=str(getattr(value, "annotation")),
        args=str(getattr(value, "args")) if getattr(value, "args", None) is not None else None,
        imports=tuple(str(item) for item in getattr(value, "imports", ()) or ()),
    )
