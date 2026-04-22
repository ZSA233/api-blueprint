from __future__ import annotations

import inspect
from typing import Any, Callable, Optional

from fastapi import Body, Depends, Form, Query, Request
from pydantic import BaseModel

from api_blueprint.engine.schema import Field, HeaderModel, iter_model_vars, resolve_field


def make_endpoint(
    handler: Callable[..., Any],
    query_model: Optional[type[BaseModel]] = None,
    form_model: Optional[type[BaseModel]] = None,
    json_model: Optional[type[BaseModel]] = None,
    header_model: Optional[type[HeaderModel]] = None,
):
    args: list[inspect.Parameter] = []

    if query_model:
        args.append(
            inspect.Parameter(
                "q",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=query_model,
                default=Query(...),
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
