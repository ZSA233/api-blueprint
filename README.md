# Api-Blueprint

[![GitHub Stars](https://img.shields.io/github/stars/zsa233/api-blueprint)](https://github.com/zsa233/api-blueprint/stargazers)
[![License](https://img.shields.io/github/license/zsa233/api-blueprint)](LICENSE)


🌍 语言: 中文 | [English](README_EN.md)


## 简介

api-blueprint蓝图致力于通过一份蓝图来规范关联的后端/前端/客户端等编程语言的proto结构生成.同时也是为了在接用ai来开的时候,能够


## 蓝图设计

1. 使用python语言进行编写和描述


2. 通过编写`Blueprint`来定义一个根节点蓝图
```python

from api_blueprint.includes import * # 一次性引入蓝图常用的类型

from blueprints.errors import CommonErr # 蓝图中实现的error类型
from blueprints.headers import GeneralHeader # 蓝图实现的HEADER

# 接口设计是为了3层目录实现的:
#   /{Blueprint.root}/{RouterGroup.branch}/{Router.leaf}
# 如果要定义的接口层级不足3级的时候,只要RouterGroup.branch/Router.leaf 是空即可实现
apibp = Blueprint(
    root='/api',    # 定义 {Blueprint.root} 层
    tags=['api'],   # 
    providers=[ # provider 是一个请求响应完成所需要的驱动处理器(可以简单理解成中间件实现)
        provider.Req(),
        provider.Auth(),
        provider.Handle(),
        provider.Rsp(),
    ],
    errors=[
        CommonErr, # 错误码定义
    ],
    response_wrapper=GeneralWrapper, # 响应的结构wrapper,GeneralWrapper(code, message, data)
    headers=GeneralHeader, # 用于请求头定义,建议使用APIKeyHeader可以生成更好管理的请求头设置
)

```

3. 定义路径接口(大部分接口定义都沿用fastapi中的Field参数定义规范):
```python
from api_blueprint.includes import *
from blueprints.app import apibp

# 定义一个结构体
class ApiDemoSubA(Model):
    hello   = Map[String, Int](description='hello')


class ApiDemoA(Model):
    a       = Int(description='a')
    bc      = String(description='bc')
    efg     = Float32(description='efg')
    hijk    = Array[Uint](description='hijk')
    lmnop   = Array[ApiDemoSubA](description='lmnop', omitempty=True)


with apibp.group('/demo') as views: # 定义 {RouterGroup.branch} 层,结合apibp的定义,那么前缀是: /api/demo


    views.GET(
        '/abc', # 定义 {Router.leaf},结合起来那么最后是: /api/demo/abc
        summary='这是abc的summary', description='这是abc的description'
    ).ARGS(
        arg1    = Bool(description='arg1', default=True),
        arg2    = Float(description='arg2', default=6.666),
    ).RSP(ApiDemoA) # 在参数定义中,可以混合 Model引用或者 逐个字段定义.

```

4. 通过蓝图配置文件`api-blueprint.toml`来定义蓝图配置信息:
```toml
[blueprint]
docs_server = '0.0.0.0:2332'  # fastapi生成的openapi文档服务,可以通过一 api-doc-server 启动,或者 `api-gen-{lang} -d` 带上-d 来启动, 进入 http://localhost:2332/docs 即可浏览openapi文档服务
docs_domain = '' # 当一个蓝图项目中有多个fastapi-app的时候,会先生成一个api hub,如果指定的话,其中hub会使用该domain来重定向到对应的api文档服务
entrypoints = [
    'blueprints.app:*',   # 用于注册对应的Blueprint蓝图模块,使用*通配符来注册 blueprint.app包下面的所有Blueprint蓝图
]

[golang] 
codegen_output = 'golang' # 相对于api-blueprint.toml配置的golang项目代码生成输出路径
upstream = 'http://localhost:2333' # golang的上游服务,用于openapi开启的文档服务的try it out请求转发

[typescript]
codegen_output = 'typescript'
upstream = 'http://localhost:2333'
base_url = 'http://localhost:2333' # 生成client.ts默认的fetch基准地址

```

5. 

## 支持的语言

| 编程语言 | 状态 | 命令 | 例子 |
|:---------|:-----:|:-----|:-----|
| golang | 可用     | api-gen-golang | examples/golang |
| typescript | 预览     | api-gen-typescript | examples/typescript |


## 规范设计
### Golang

#### 文件组织结构
```md
golang
├── errors/
│   ├── errors/
│   │   └── {err_class_name}
│   │       └── gen_errors.go
│   └── errors.go
│
├── views
│   ├── {Blueprint.root}/
│   │   ├── {RouterGroup.branch}/
│   │   │   ├── gen_interface.go
│   │   │   ├── gen_protos.go
│   │   │   └── impl.go
│   │   │
│   │   ├── protos/
│   │   │   └── gen_protos.go
│   │   │
│   │   └── gen_blueprint.go
│   │
│   ├── provider/
│   │   ├── gen_auth.go
│   │   ├── gen_handle.go
│   │   ├── ...
│   │   ├── impl_auth.go
│   │   ├── impl_handle.go
│   │   └── ...
│   │
│   └── engine.go
└── ...

```


1. errors: 生成的公共错误码定义protos
2. views: 接口定义和实现
    - gen_interface.go: 接口定义interface和gin框架的接口注册实现
    - gen_protos.go: {RouterGroup.branch}层级的分组的protos定义
    - impl.go: 接口业务实现
    - protos/gen_protos.go: 公共 protos
    - gen_blueprint.go: 蓝图newer
    - engine.go: gin引擎封装
3. provider: 中间件实现,任何业务中间件修改impl_{provider}.go

### TypeScript

#### 文件组织结构
```text
typescript
├── {Blueprint.root}/
│   ├── shared/
│   │   ├── models.ts   # 蓝图级公共模型 / 响应包装
│   │   └── index.ts
│   ├── {RouterGroup.branch}/
│   │   ├── models.ts   # 当前 group 的路由契约
│   │   ├── client.ts   # 仅包含该 group 接口的 fetch 客户端
│   │   └── index.ts
│   └── index.ts        # 汇总 re-export
└── ...
```

- shared/models.ts 会集中列出蓝图下的共有结构体、枚举与 ResponseWrapper；每个 group 下的 models.ts 只包含该 group 的 REQ/RSP/CTX/别名等契约定义，并在需要时自动 import shared 模型避免命名冲突。
- shared/client.ts 内置 `BaseClient`，封装了 fetch/headers/query/form 请求逻辑，所有 group 的 `XXXClient` 仅继承并声明各自的接口方法，避免重复代码。
- 每个 group 会生成独立的 `XXXClient` 类（如 `DemoClient`、`HelloClient`），接口方法仅注册到所属 group，支持 query/form/json/body 组合参数，自动推导响应封装器，并为 WebSocket 接口生成 `connectXxx` 方法。
- 各级 index.ts 负责导出 models / client，同时 {Blueprint.root}/index.ts 统一导出 Shared 以及所有 group 命名空间，方便前端按需 import。
- 运行 `api-gen-typescript -c examples/api-blueprint.toml` 即可在 `examples/typescript` 下查看完整示例目录。

# 例子

[examples](./examples)
