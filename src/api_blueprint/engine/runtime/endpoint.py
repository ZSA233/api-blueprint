from __future__ import annotations

import inspect
from typing import Any, Callable, Optional

from fastapi import Body, Depends, Form, Path, Query, Request
from pydantic import BaseModel

from api_blueprint.engine.schema import Field, HeaderModel, iter_model_vars, resolve_field


def make_endpoint(
    handler: Callable[..., Any],
    path_model: Optional[type[BaseModel]] = None,
    query_model: Optional[type[BaseModel]] = None,
    form_model: Optional[type[BaseModel]] = None,
    json_model: Optional[type[BaseModel]] = None,
    header_model: Optional[type[HeaderModel]] = None,
):
    args: list[inspect.Parameter] = []

    if path_model:
        path_args: list[inspect.Parameter] = []
        for model_field_name, model_field in path_model.model_fields.items():
            path_name = str(model_field.alias or model_field_name)
            path_args.append(
                inspect.Parameter(
                    path_name,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=model_field.annotation or Any,
                    default=Path(..., description=model_field.description),
                )
            )

        if path_args:
            async def path_builder(**kwargs: Any):
                return kwargs

            path_builder.__signature__ = inspect.Signature(path_args)
            args.append(
                inspect.Parameter(
                    "path",
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=dict,
                    default=Depends(path_builder),
                )
            )

    if query_model:
        query_args: list[inspect.Parameter] = []
        for model_field_name, model_field in query_model.model_fields.items():
            query_name = str(model_field.alias or model_field_name)
            default_value = ... if model_field.is_required() else model_field.default
            query_args.append(
                inspect.Parameter(
                    model_field_name,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=model_field.annotation or Any,
                    default=Query(
                        default_value,
                        description=model_field.description,
                        alias=query_name if query_name != model_field_name else None,
                        json_schema_extra=model_field.json_schema_extra,
                    ),
                )
            )

        if query_args:
            async def query_builder(**kwargs: Any):
                return kwargs

            query_builder.__signature__ = inspect.Signature(query_args)
            args.append(
                inspect.Parameter(
                    "q",
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=dict,
                    default=Depends(query_builder),
                )
            )

    if form_model:
        args.append(
            inspect.Parameter(
                "f",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=form_model,
                default=Form(...),
            )
        )

    if json_model:
        args.append(
            inspect.Parameter(
                "j",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=json_model,
                default=Body(...),
            )
        )

    if header_model:
        header_args: list[inspect.Parameter] = []
        for name, field in iter_model_vars(header_model):
            if not isinstance(field, Field):
                continue
            header_args.append(
                inspect.Parameter(
                    name,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=str,
                    default=resolve_field(field)[1],
                )
            )

        if header_args:
            async def header_builder(**kwargs: Any):
                return kwargs

            header_builder.__signature__ = inspect.Signature(header_args)
            args.append(
                inspect.Parameter(
                    "header",
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=dict,
                    default=Depends(header_builder),
                )
            )

    args.append(
        inspect.Parameter(
            "request",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=Request,
            default=None,
        )
    )

    async def endpoint(**kwargs: Any):
        result = handler(**kwargs)
        if inspect.isawaitable(result):
            result = await result
        return result

    endpoint.__signature__ = inspect.Signature(args)
    return endpoint
