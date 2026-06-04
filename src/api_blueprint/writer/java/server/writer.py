from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
import json

from api_blueprint.writer.java.blueprint import JavaApiGroup, JavaRoute
from api_blueprint.writer.java.planner import JavaBlueprintPlan, JavaRouteGroupPlan
from api_blueprint.writer.java.writer import JAVA_SERVER_GENERATED_HEADER, JavaBaseWriter


@dataclass(frozen=True)
class JavaSpringPolicyBinding:
    id: str
    annotation: str
    args: str | None = None
    imports: tuple[str, ...] = ()


@dataclass(frozen=True)
class JavaSpringRouteBinding:
    operation_id: str
    annotation: str | None = None
    policies: tuple[str, ...] = ()
    request_binding: str = "generated"
    response_binding: str = "generated"


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
        spring_contract_mode: str = "strict-boundary",
        spring_policies: Sequence[object] = (),
        spring_route_bindings: Sequence[object] = (),
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
        self.spring_policies = tuple(_coerce_policy(policy) for policy in spring_policies)
        self.spring_route_bindings = tuple(_coerce_route_binding(binding) for binding in spring_route_bindings)
        self.spring_public_paths = tuple(spring_public_paths)
        self.spring_exclude_server_paths = tuple(spring_exclude_server_paths)

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

    def _write_group_models(self, group_plan: JavaRouteGroupPlan, context: dict[str, object]) -> None:
        group = group_plan.group
        for stale_name in (
            f"{group.types_class}.java",
            f"{group.generated_service_class}.java",
            f"{group.stub_class}.java",
            f"{group.service_class}Stub.java",
        ):
            self._unlink_generated_file(group_plan.directory / stale_name)
        types_dir = self.root_dir(context["bp"]) / "types" / group.package_path  # type: ignore[arg-type]
        self._write_generated(
            types_dir / f"{group.types_class}.java",
            "GenApiGroupTypes.java",
            {**context, "group": group},
            "server/types",
        )

    def _write_server_group(self, group_plan: JavaRouteGroupPlan, context: dict[str, object]) -> None:
        group = group_plan.group
        for stale_name in (
            f"{group.generated_service_class}.java",
            f"{group.stub_class}.java",
            f"{group.service_class}Stub.java",
        ):
            self._unlink_generated_file(group_plan.directory / stale_name)
        annotations_dir = self.root_dir(context["bp"]) / "annotations" / group.package_path  # type: ignore[arg-type]
        adapters_dir = self.root_dir(context["bp"]) / "adapters" / group.package_path  # type: ignore[arg-type]
        for route in group.routes:
            self._write_generated(
                annotations_dir / f"{self.route_annotation_name(route)}.java",
                "GenRouteAnnotation.java",
                {**context, "group": group, "route": route},
                "server/annotations",
            )
        self._write_generated(
            adapters_dir / f"{self.group_adapters_class(group)}.java",
            "GenApiGroupAdapters.java",
            {**context, "group": group},
            "server/adapters",
        )

    def binding_for_route(self, route: JavaRoute) -> JavaSpringRouteBinding | None:
        keys = {route.route_id, route.operation, route.method_name}
        for binding in self.spring_route_bindings:
            if binding.operation_id in keys:
                return binding
        return None

    def policies_for_route(self, route: JavaRoute) -> tuple[JavaSpringPolicyBinding, ...]:
        binding = self.binding_for_route(route)
        if binding is None:
            return ()
        policies_by_id = {policy.id: policy for policy in self.spring_policies}
        return tuple(policies_by_id[policy_id] for policy_id in binding.policies if policy_id in policies_by_id)

    def route_annotation_name(self, route: JavaRoute) -> str:
        binding = self.binding_for_route(route)
        if binding is not None and binding.annotation:
            return binding.annotation
        return f"Gen{route.operation_type_name}"

    def route_annotation_package(self, bp: Any, group: JavaApiGroup) -> str:
        return f"{bp.root_package}.annotations.{group.package_suffix}"

    def route_annotation_class(self, bp: Any, group: JavaApiGroup, route: JavaRoute) -> str:
        return f"{self.route_annotation_package(bp, group)}.{self.route_annotation_name(route)}"

    def group_types_package(self, bp: Any, group: JavaApiGroup) -> str:
        return f"{bp.root_package}.types.{group.package_suffix}"

    def group_types_ref(self, bp: Any, group: JavaApiGroup) -> str:
        return f"{self.group_types_package(bp, group)}.{group.types_class}"

    def group_adapters_package(self, bp: Any, group: JavaApiGroup) -> str:
        return f"{bp.root_package}.adapters.{group.package_suffix}"

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

    def policy_annotation_expr(self, policy: JavaSpringPolicyBinding) -> str:
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
        binding = self.binding_for_route(route)
        if self.spring_contract_mode == "annotations-only":
            return "annotations-only"
        return binding.request_binding if binding is not None else "generated"

    def route_response_binding(self, route: JavaRoute) -> str:
        binding = self.binding_for_route(route)
        if self.spring_contract_mode == "annotations-only":
            return "annotations-only"
        return binding.response_binding if binding is not None else "generated"

    def spring_contract_runtime_mode(self) -> str:
        return {
            "audit": "AUDIT",
            "public": "PUBLIC",
            "strict": "STRICT",
            "strict-boundary": "PUBLIC",
            "annotations-only": "PUBLIC",
        }.get(self.spring_contract_mode, "PUBLIC")

    def _server_contract_type_name(self, bp: Any, group: JavaApiGroup, type_name: str) -> str:
        if type_name.startswith(f"{group.types_class}."):
            return f"{self.group_types_ref(bp, group)}.{type_name.split('.', 1)[1]}"
        if type_name.startswith("GenApiTypes."):
            return f"{bp.root_package}.runtime.{type_name}"
        return type_name


def _coerce_policy(value: object) -> JavaSpringPolicyBinding:
    if isinstance(value, JavaSpringPolicyBinding):
        return value
    if isinstance(value, Mapping):
        return JavaSpringPolicyBinding(
            id=str(value.get("id") or ""),
            annotation=str(value.get("annotation") or ""),
            args=str(value["args"]) if value.get("args") is not None else None,
            imports=tuple(str(item) for item in value.get("imports", ()) or ()),
        )
    return JavaSpringPolicyBinding(
        id=str(getattr(value, "id")),
        annotation=str(getattr(value, "annotation")),
        args=str(getattr(value, "args")) if getattr(value, "args", None) is not None else None,
        imports=tuple(str(item) for item in getattr(value, "imports", ()) or ()),
    )


def _coerce_route_binding(value: object) -> JavaSpringRouteBinding:
    if isinstance(value, JavaSpringRouteBinding):
        return value
    if isinstance(value, Mapping):
        return JavaSpringRouteBinding(
            operation_id=str(value.get("operation_id") or ""),
            annotation=str(value["annotation"]) if value.get("annotation") is not None else None,
            policies=tuple(str(item) for item in value.get("policies", ()) or ()),
            request_binding=str(value.get("request_binding") or "generated"),
            response_binding=str(value.get("response_binding") or "generated"),
        )
    return JavaSpringRouteBinding(
        operation_id=str(getattr(value, "operation_id")),
        annotation=str(getattr(value, "annotation")) if getattr(value, "annotation", None) is not None else None,
        policies=tuple(str(item) for item in getattr(value, "policies", ()) or ()),
        request_binding=str(getattr(value, "request_binding", "generated")),
        response_binding=str(getattr(value, "response_binding", "generated")),
    )
