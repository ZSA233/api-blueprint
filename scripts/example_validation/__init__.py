from __future__ import annotations

from .cli import build_parser, main
from .compile import (
    compile_generated_examples,
    compile_generated_grpc_examples,
    compile_repo_examples,
    compile_repo_grpc_examples,
    compile_wails_hello_example,
)
from .constants import *
from .generate import (
    regenerate_blueprint_examples,
    regenerate_blueprint_golang_suite_examples,
    regenerate_blueprint_java_suite_examples,
    regenerate_grpc_examples,
    regenerate_repo_blueprint_examples,
    regenerate_repo_grpc_examples,
    regenerate_repo_wails_hello_example,
    regenerate_wails_hello_example,
)
from .models import (
    BlueprintExampleWorkspace,
    ExampleValidationError,
    ExampleValidationMode,
    ExampleValidationScope,
    GrpcExampleWorkspace,
    WailsHelloExampleWorkspace,
)
from .runner import (
    compile_blueprint_examples,
    compile_examples,
    compile_grpc_examples,
    compile_wails_hello_examples,
    refresh_examples,
    run_golang_suite_examples,
    run_java_suite_examples,
    validate_blueprint_examples,
    validate_examples,
    validate_grpc_examples,
    validate_wails_hello_examples,
)
from .snapshot import (
    validate_example_snapshots,
    validate_grpc_snapshots,
    validate_wails_hello_snapshots,
)
from .tools import (
    collect_missing_validation_requirements,
    ensure_validation_requirements,
    resolve_gradle_bin,
    resolve_wails_bin,
)
from .workspace import (
    _blueprint_workspace,
    _grpc_workspace,
    _prepare_blueprint_outputs,
    _prepare_contract_outputs,
    _prepare_grpc_outputs,
    _prepare_wails_hello_outputs,
    _wails_hello_workspace,
    prepare_blueprint_workspace,
    prepare_grpc_workspace,
    prepare_wails_hello_workspace,
)
