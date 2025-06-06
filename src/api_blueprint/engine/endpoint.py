import inspect
from typing import Any, Callable, List, Optional, Type, Annotated
from fastapi import Body, Form, Query, Header, Request, Depends, Security
from pydantic import BaseModel
from pydantic_core import PydanticUndefined
from api_blueprint.engine import model


def make_endpoint(
    handler: Callable[..., Any],
    query_model: Optional[Type[BaseModel]] = None,
    form_model:  Optional[Type[BaseModel]] = None,
    json_model:  Optional[Type[BaseModel]] = None,
    header_model: Optional[Type[model.HeaderModel]] = None,
):
    args: List[inspect.Parameter] = []

    # q: QueryModel = Query()
    if query_model:
        args.append(inspect.Parameter(
            "q",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=query_model,
            default=Query(...),
        ))

    # f: FormModel = Form()
    if form_model:
        args.append(inspect.Parameter(
            "f",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=form_model,
            default=Form(...),
        ))

    # j: JSONModel = Body(...)
    if json_model:
        args.append(inspect.Parameter(
            "j",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=json_model,
            default=Body(...),
        ))

    # header
    if header_model:
        header_args = []
        for name, field in model.iter_model_vars(header_model):
            if not isinstance(field, model.Field):
                continue
            
            header_args.append(inspect.Parameter(
                name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=str,
                default=model.resolve_field(field)[1],
            ))

        if header_args:
            async def header_builder(**kwargs):
                return kwargs
            
            header_builder.__signature__ = inspect.Signature(header_args)

            args.append(inspect.Parameter(
                'header',
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=dict,
                default=Depends(header_builder),
            ))

    args.append(inspect.Parameter(
        'request',
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=Request,
        default=None,
    ))

    async def endpoint(**kwargs):
        result = handler(**kwargs)
        if inspect.isawaitable(result):
            result = await result
        return result

    endpoint.__signature__ = inspect.Signature(args)

    return endpoint

