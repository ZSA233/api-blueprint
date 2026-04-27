package com.example.apiblueprint.models

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
public data class HelloAbcQuery(
    public val arg1: Boolean? = null,
    public val arg3: String? = null,
    public val arg2: Float? = null,
    public val type: WsMsgTypeEnum
)

public typealias HelloAbcResponse = Map<String, ApiHelloMap>

@Serializable
public data class HelloHelloWayQuery(
    public val arg1: HelloWayEnum? = null
)

public typealias HelloListEnumResponse = List<MapEnum>

public typealias HelloMapEnumResponse = Map<String, ApiHelloMap>

public typealias HelloStringEmunResponse = MapEnum

public typealias HelloStringResponse = String

public typealias HelloUint64Response = Long
