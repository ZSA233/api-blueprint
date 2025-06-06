# Api-Blueprint

[![GitHub Stars](https://img.shields.io/github/stars/zsa233/api-blueprint)](https://github.com/zsa233/api-blueprint/stargazers)
[![License](https://img.shields.io/github/license/zsa233/api-blueprint)](LICENSE)


🌍 语言: 中文 | [English](README_EN.md)

> [!WARNING]
> 目前处于开发探索阶段,其中golang代码生成和openapi文档服务相对成熟.其他语言等有更好的设计灵感再补充完善.

## 简介

api-blueprint蓝图致力于通过一份蓝图来规范关联的后端/前端/客户端等编程语言的proto结构生成.同时也是为了在接用ai来开的时候,能够


## 蓝图设计

1. 蓝图设计本质上是一个py开发的项目,所以任何符合py的项目开发引用实现习惯都是被允许的.


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

```

5. 

## 支持的语言

| 编程语言 | 状态 | 命令 | 例子 |
|:---------|:-----:|:-----|:-----|
| golang | 可用     | api-gen-golang | examples/golang |
| react | 开发中     | api-gen-react | examples/react |


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

# 例子
> 详细的例子查看 [golang](./examples/golang)
```golang
// Code generated by api-gen-golang; DO NOT EDIT.

package demo

import (
	views "demo/views"
	"github.com/gin-gonic/gin"
)

type RouterInterface interface {
	Abc(ctx *CTX_Abc, req *REQ_Abc) (rsp *RSP_Abc, err error)
	TestPost(ctx *CTX_TestPost, req *REQ_TestPost) (rsp *RSP_TestPost, err error)
	F1put(ctx *CTX_F1put, req *REQ_F1put) (rsp *RSP_F1put, err error)
	Delete(ctx *CTX_Delete, req *REQ_Delete) (rsp *RSP_Delete, err error)
	Ws(ctx *CTX_Ws, req *REQ_Ws) (rsp *RSP_Ws, err error)
	PostDeprecated(ctx *CTX_PostDeprecated, req *REQ_PostDeprecated) (rsp *RSP_PostDeprecated, err error)
}

func NewImpl(eng *gin.Engine) *Router {
	impl := NewRouter()

	views.GET("/api/demo/abc", impl.Abc, eng, "req=Q|auth|handle|rsp=json@GeneralWrapper")
	views.POST("/api/demo/test_post", impl.TestPost, eng, "req=J|auth|handle|rsp=json@GeneralWrapper")
	views.PUT("/api/demo/1put", impl.F1put, eng, "req=QJ|auth|handle|rsp=json@GeneralWrapper")
	views.DELETE("/api/demo/delete$", impl.Delete, eng, "req=Q|auth|handle|rsp=xml@GeneralWrapper")
	views.WS("/api/demo/ws", impl.Ws, eng, "req=Q|auth|handle|rsp=json@GeneralWrapper")
	views.POST("/api/demo/post_deprecated", impl.PostDeprecated, eng, "req=J|auth|handle|rsp=json@GeneralWrapper")

	return impl
}

```

# impl
```golang
package demo

import (
	"fmt"
)

type Router struct{}

func NewRouter() *Router {
	return &Router{}
}

func (impl *Router) Abc(
	ctx *CTX_Abc, req *REQ_Abc,
) (rsp *RSP_Abc, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) TestPost(
	ctx *CTX_TestPost, req *REQ_TestPost,
) (rsp *RSP_TestPost, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) F1put(
	ctx *CTX_F1put, req *REQ_F1put,
) (rsp *RSP_F1put, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) Delete(
	ctx *CTX_Delete, req *REQ_Delete,
) (rsp *RSP_Delete, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) Ws(
	ctx *CTX_Ws, req *REQ_Ws,
) (rsp *RSP_Ws, err error) {
	return nil, fmt.Errorf("not implemented")
}

func (impl *Router) PostDeprecated(
	ctx *CTX_PostDeprecated, req *REQ_PostDeprecated,
) (rsp *RSP_PostDeprecated, err error) {
	return nil, fmt.Errorf("not implemented")
}

```



## 更多例子

[examples](./examples)

