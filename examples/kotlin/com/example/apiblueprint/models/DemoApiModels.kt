package com.example.apiblueprint.models

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
public data class AnonFunc1putAnonKv(
    public val kv1: Int,
    public val kv2: List<Double>
)

@Serializable
public data class DemoAbcQuery(
    public val arg1: Boolean? = null,
    public val arg3: String? = null,
    public val arg2: Float? = null
)

@Serializable
public data class DemoFunc1putJson(
    public val req1: String,
    public val req2: Int? = null
)

@Serializable
public data class DemoFunc1putQuery(
    public val arg1: String? = null,
    public val arg2: Float? = null,
    public val arg3: String? = null
)

@Serializable
public data class DemoFunc1putResponse(
    public val list: List<String>,
    @SerialName("anon_kv")
    public val anonKv: AnonFunc1putAnonKv
)

public typealias DemoMapModelResponse = Map<Int, ApiDemoMap>

@Serializable
public data class DemoPostDeprecatedJson(
    public val req1: String,
    public val req2: Int? = null
)

@Serializable
public data class DemoPostDeprecatedResponse(
    public val list: List<String>
)

@Serializable
public data class DemoRawResponse(
    public val list: List<String>,
    public val list2: Map<Long, List<ApiDemoA>>
)

@Serializable
public data class DemoTestPostJson(
    public val req1: String,
    public val req2: Int? = null
)

@Serializable
public data class DemoTestPostResponse(
    public val list: List<String>,
    public val map: Map<String, ApiDemoMap>
)
