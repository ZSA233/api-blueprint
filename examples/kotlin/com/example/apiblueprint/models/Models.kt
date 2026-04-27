package com.example.apiblueprint.models

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
public data class ApiDemoA(
    public val bc: String,
    public val a: Int,
    public val efg: Float,
    public val hijk: List<Int>,
    public val lmnop: List<ApiDemoSubA>? = null,
    @SerialName("enum_color")
    public val enumColor: ColorEnum? = null,
    @SerialName("enum_status")
    public val enumStatus: StatusEnum,
    @SerialName("enum_list")
    public val enumList: List<StatusEnum>
)

@Serializable
public data class ApiDemoMap(
    public val haha: Long
)

@Serializable
public data class ApiDemoSubA(
    public val hello: Map<String, Int>,
    public val amap: List<ApiDemoMap>
)

@Serializable
public data class ApiHelloMap(
    public val haha: Long
)

@Serializable
public enum class ColorEnum {
    @SerialName("red")
    RED,
    @SerialName("green")
    GREEN,
    @SerialName("blue")
    BLUE
}

@Serializable
public data class GeneralResponse<T>(
    public val code: Int,
    public val message: String? = null,
    public val data: T
)

@Serializable
public enum class HelloWayEnum {
    @SerialName("ASD")
    ASD
}

@Serializable
public enum class MapEnum {
    @SerialName("a")
    A,
    @SerialName("b")
    B
}

@Serializable
public enum class StatusEnum {
    @SerialName("1")
    PENDING,
    @SerialName("2")
    RUNNING,
    @SerialName("3")
    FINISHED
}

@Serializable
public enum class WsMsgTypeEnum {
    @SerialName("ping")
    PING,
    @SerialName("pong")
    PONG,
    @SerialName("join")
    JOIN,
    @SerialName("leave")
    LEAVE,
    @SerialName("forgeround")
    FORGEROUND,
    @SerialName("upgrade")
    UPGRADE
}
