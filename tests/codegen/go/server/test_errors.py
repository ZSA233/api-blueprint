from __future__ import annotations

from .helpers import *


def test_golang_response_envelope_preserves_generic_type_parameters():
    envelope = GolangResponseEnvelope("RSP_JSON", CodeMessageDataEnvelope)
    assert envelope.proto_def_name == "RSP_JSON_CodeMessageDataEnvelope[T any]"
    assert envelope.generic_types(True) == "[T any]"

@pytest.mark.toolchain_smoke
def test_golang_server_error_mapper_option_overrides_default(tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP()

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    rsp_provider = (output_dir / "providers" / "gen_rsp.go").read_text(encoding="utf-8")
    executor_provider = (output_dir / "providers" / "gen_executor.go").read_text(encoding="utf-8")
    assert "type ErrorMappingContext struct" in rsp_provider
    assert "Route     RouteInfo" in rsp_provider
    assert "Transport TransportKind" in rsp_provider
    assert "type ErrorMapperFunc func(ErrorMappingContext, error) (*errors.ApiErrorPayload, bool)" in rsp_provider
    assert "type RuntimeOption func(*RuntimeOptions)" in rsp_provider
    assert "func WithErrorMapper(mapper ErrorMapperFunc) RuntimeOption" in rsp_provider
    assert "var ErrorMapper ErrorMapperFunc" not in rsp_provider
    assert "if ErrorMapper != nil" not in rsp_provider
    assert "options ...RuntimeOption" in executor_provider
    assert "runtime := NewRuntimeOptions(options...)" in executor_provider

    (output_dir / "providers" / "error_mapper_test.go").write_text(
        """
package providers

import (
	stdErrors "errors"
	"testing"

	runtimeerrors "example.com/generated/golang/runtime/errors"
)

type customErr struct{}

func (customErr) Error() string { return "custom" }

type codedErr struct{}

func (codedErr) Error() string { return "coded" }
func (codedErr) Code() int { return 409 }
func (codedErr) Message() string { return "coded message" }

func TestErrorMapperOptionOverridesDefault(t *testing.T) {
	executor := NewRouteExecutor[any, any, any, any](
		RouteInfo{Root: "api", RouteID: "api.demo.get.ping", Transport: TransportHTTP},
		"rsp=json@CodeMessageDataEnvelope",
		nil,
		WithErrorMapper(func(ctx ErrorMappingContext, err error) (*runtimeerrors.ApiErrorPayload, bool) {
			if ctx.Route.RouteID != "api.demo.get.ping" || ctx.Transport != TransportHTTP {
				t.Fatalf("unexpected mapper context: %#v", ctx)
			}
			if _, ok := err.(customErr); ok {
				return &runtimeerrors.ApiErrorPayload{
					Code:    418,
					Message: "mapped",
					Toast: runtimeerrors.ToastPayload{
						Level:   "warning",
						Default: "mapped",
					},
				}, true
			}
			return nil, false
		}),
	)

	code, message, toast, payload := executor.Indexer.Rsp.unwrapError(customErr{})
	if code != 418 || message != "mapped" || payload == nil || payload.Code != 418 {
		t.Fatalf("mapper not applied: code=%d message=%q payload=%#v", code, message, payload)
	}
	if toast["level"] != "warning" || toast["default"] != "mapped" {
		t.Fatalf("mapper toast not applied: %#v", toast)
	}

	code, message, _, payload = executor.Indexer.Rsp.unwrapError(codedErr{})
	if code != 409 || message != "coded message" || payload == nil || payload.Code != 409 {
		t.Fatalf("code carrier fallback changed: code=%d message=%q payload=%#v", code, message, payload)
	}

	code, message, _, payload = executor.Indexer.Rsp.unwrapError(stdErrors.New("boom"))
	if code != -1 || message != "internal server error" || payload == nil || payload.Code != -1 {
		t.Fatalf("default fallback changed: code=%d message=%q payload=%#v", code, message, payload)
	}
}

func TestNilErrorDoesNotCallMapper(t *testing.T) {
	called := false
	executor := NewRouteExecutor[any, any, any, any](
		RouteInfo{Root: "api", RouteID: "api.demo.get.ping", Transport: TransportHTTP},
		"rsp=json@CodeMessageDataEnvelope",
		nil,
		WithErrorMapper(func(ctx ErrorMappingContext, err error) (*runtimeerrors.ApiErrorPayload, bool) {
			called = true
			return nil, false
		}),
	)

	code, message, _, payload := executor.Indexer.Rsp.unwrapError(nil)
	if called {
		t.Fatal("mapper should not be called for nil error")
	}
	if code != 0 || message != "" || payload != nil {
		t.Fatalf("nil error fallback changed: code=%d message=%q payload=%#v", code, message, payload)
	}
}
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    if shutil.which("go") is not None:
        result = subprocess.run(
            ["go", "test", "./providers"],
            cwd=output_dir,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr

@pytest.mark.toolchain_smoke
def test_golang_writer_generates_only_declared_error_models(tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    class UsedErr(Model):
        BOOM = Error(
            1001,
            "boom",
            toast=Toast(
                key="demo.boom",
                default="操作失败，请稍后再试",
                level="warning",
            ),
        )

    class UnusedErr(Model):
        NOISE = Error(1002, "noise")

    bp = Blueprint(root="/api", errors=[UsedErr])
    with bp.group("/demo") as views:
        views.GET("/ping").RSP()

    stale_catalog = output_dir / "runtime" / "errors" / "gen_error_lookup.go"
    stale_catalog.parent.mkdir(parents=True)
    stale_catalog.write_text(
        "// Code generated by api-blueprint (Golang); DO NOT EDIT.\n\npackage errors\n\nvar CatalogByID = map[string]CatalogEntry{}\n",
        encoding="utf-8",
    )

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    group_errors = (output_dir / "runtime" / "errors" / "used_err" / "gen_errors.go").read_text(encoding="utf-8")
    runtime_errors = (output_dir / "runtime" / "errors" / "gen_errors.go").read_text(encoding="utf-8")
    assert "BOOM = e.NewApiError(e.ErrorMeta{" in group_errors
    assert 'ID:      "UsedErr.BOOM",' in group_errors
    assert 'Group:   "UsedErr",' in group_errors
    assert 'Key:     "BOOM",' in group_errors
    assert "e.ToastSpec{\n" in group_errors
    assert 'Key:     "demo.boom",' in group_errors
    assert 'Default: "操作失败，请稍后再试",' in group_errors
    assert "type ApiError struct" in runtime_errors
    assert "type ErrorMeta struct" in runtime_errors
    assert "type ApiErrorPayload struct" in runtime_errors
    assert "type ApiErrorCodeCarrier interface" in runtime_errors
    assert "type ToastProvider interface" in runtime_errors
    assert "func (e ApiError) WithToast(toast ToastPayload) *ApiError" in runtime_errors
    assert "CatalogByID" not in runtime_errors
    assert "CatalogEntry" not in runtime_errors
    assert "\\u64cd" not in group_errors
    assert (output_dir / "runtime" / "errors" / "errors.go").is_file()
    assert not (output_dir / "runtime" / "errors" / "gen_error_lookup.go").exists()
    assert not (output_dir / "runtime" / "errors" / "unused_err").exists()

    if shutil.which("go") is not None:
        (output_dir / "runtime" / "errors" / "toast_test.go").write_text(
            """
package errors

import "testing"

func TestWithToastDoesNotMutateOriginal(t *testing.T) {
	original := NewApiError(ErrorMeta{
		ID:      "UsedErr.BOOM",
		Group:   "UsedErr",
		Key:     "BOOM",
		Code:    1001,
		Message: "boom",
		Toast: ToastSpec{
			Key:     "demo.boom",
			Level:   "warning",
			Default: "操作失败，请稍后再试",
		},
	})
	override := original.WithToast(ToastPayload{
		Key:  "demo.boom.enterprise",
		Text: "企业账号异常，请联系管理员",
	})
	if original.Toast().Key != "demo.boom" || original.Toast().Text != "" {
		t.Fatalf("original toast was mutated: %#v", original.Toast())
	}
	if override.Toast().Key != "demo.boom.enterprise" || override.Toast().Text == "" {
		t.Fatalf("override toast not applied: %#v", override.Toast())
	}
}
            """.strip()
            + "\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            ["go", "test", "./runtime/errors"],
            cwd=output_dir,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
