from __future__ import annotations

import re
from typing import ClassVar, Generic, TypeVar

from .helpers import *
from api_blueprint.engine import ResponseEnvelope
from api_blueprint.engine.schema import Field, Int
from api_blueprint.engine.runtime.wrappers import EnvelopeToastPayload

TM = TypeVar("TM", bound=Model)


def test_golang_response_envelope_preserves_generic_type_parameters():
    envelope = GolangResponseEnvelope("RSP_JSON", CodeMessageDataEnvelope)
    assert envelope.proto_def_name == "RSP_JSON_CodeMessageDataEnvelope[T any]"
    assert envelope.generic_types(True) == "[T any]"


@pytest.mark.toolchain_smoke
def test_golang_server_success_response_meta_overrides_envelope(tmp_path):
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

    class ToastEnvelope(ResponseEnvelope, Generic[TM]):
        code = Int(description="status")
        message = String(description="message")
        toast = EnvelopeToastPayload(description="toast", omitempty=True)
        data: TM = Field(description="payload")

        __envelope_kind__: ClassVar[str] = "code_message_data"
        __error_identity__: ClassVar[str] = "none"
        __success_code__: ClassVar[int] = 200
        __success_message__: ClassVar[str] = "ok"
        __envelope_fields__: ClassVar[dict[str, str]] = {
            "code": "code",
            "message": "message",
            "toast": "toast",
            "data": "data",
        }

        @classmethod
        def create(cls, data_cls: type[Model]) -> type[ResponseEnvelope]:
            return cls

        @classmethod
        def on_error(cls, err: Error) -> tuple[str, dict[str, object]]:
            return "error", {"code": err.code, "message": err.message, "data": None}

    class SaveResponse(Model):
        ok = String(description="ok")

    bp = Blueprint(root="/api", response_envelope=ToastEnvelope)
    with bp.group("/demo") as views:
        views.POST("/save").RSP(SaveResponse)

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    rsp_provider = (output_dir / "providers" / "gen_rsp.go").read_text(encoding="utf-8")
    wrapper_provider = (output_dir / "providers" / "gen_wrapper.go").read_text(encoding="utf-8")
    assert "type ToastPayload = errors.ToastPayload" in rsp_provider
    assert "type ResponseMeta struct" in rsp_provider
    assert "func (rsp *ResponseContext) SuccessToast(key string, defaultMessage string)" in rsp_provider
    assert "successMessage := meta.SuccessMessage(\"ok\")" in wrapper_provider
    assert "successToast := meta.SuccessToast()" in wrapper_provider
    assert re.search(r"Toast:\s+successToast", wrapper_provider)

    (output_dir / "providers" / "response_meta_test.go").write_text(
        """
package providers

import (
	"encoding/json"
	"errors"
	"testing"
)

type responseMetaPayload struct {
	OK string `json:"ok"`
}

func TestSuccessResponseMetaOverridesEnvelope(t *testing.T) {
	executor := NewRouteExecutor[any, any, any, responseMetaPayload](
		RouteInfo{Root: "api", RouteID: "api.demo.post.save", Transport: TransportHTTP},
		"req|handle|rsp=json@ToastEnvelope",
		func(ctx *Context[any, any, any, responseMetaPayload], req *REQ[any, any, any]) (*responseMetaPayload, error) {
			if ctx.Response == nil {
				t.Fatal("response context must be initialized")
			}
			ctx.Response.SetCode(209)
			ctx.Response.SuccessToast("demo.save.success", "保存成功")
			ctx.Response.SetToast(ToastPayload{
				Key:     "demo.save.success",
				Level:   "success",
				Default: "保存成功",
				Text:    "Saved",
			})
			return &responseMetaPayload{OK: "yes"}, nil
		},
	)
	ctx := NewHTTPContext[any, any, any, responseMetaPayload](nil, nil, nil)
	ctx.Request = NewRequestContext(&REQ[any, any, any]{}, nil)
	execErr := executor.Run(ctx)
	response, invokeErr := ctx.HandleResult()
	if execErr != nil || invokeErr != nil {
		t.Fatalf("unexpected errors: exec=%v invoke=%v", execErr, invokeErr)
	}

	_, wrapped := NewRSP_JSON(executor.Indexer.Rsp, response, invokeErr, ctx.Response.Meta())
	raw, err := json.Marshal(wrapped)
	if err != nil {
		t.Fatal(err)
	}
	var envelope map[string]any
	if err := json.Unmarshal(raw, &envelope); err != nil {
		t.Fatal(err)
	}
	if envelope["code"] != float64(209) {
		t.Fatalf("success code not applied: %#v", envelope)
	}
	if envelope["message"] != "保存成功" {
		t.Fatalf("success message did not use explicit success message: %#v", envelope)
	}
	toast, ok := envelope["toast"].(map[string]any)
	if !ok || toast["key"] != "demo.save.success" || toast["level"] != "success" || toast["default"] != "保存成功" || toast["text"] != "Saved" {
		t.Fatalf("success toast not applied: %#v", envelope)
	}
}

func TestErrorResponseIgnoresSuccessMeta(t *testing.T) {
	prov := NewRspProvider[any, any, any, responseMetaPayload]("json@ToastEnvelope", nil)
	meta := NewResponseContext()
	meta.SuccessToast("demo.save.success", "保存成功")
	_, wrapped := NewRSP_JSON(prov, nil, errors.New("boom"), meta.Meta())
	raw, err := json.Marshal(wrapped)
	if err != nil {
		t.Fatal(err)
	}
	var envelope map[string]any
	if err := json.Unmarshal(raw, &envelope); err != nil {
		t.Fatal(err)
	}
	if envelope["message"] == "保存成功" || envelope["toast"] != nil {
		t.Fatalf("error response consumed success meta: %#v", envelope)
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
