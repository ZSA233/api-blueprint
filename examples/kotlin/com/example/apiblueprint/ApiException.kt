package com.example.apiblueprint

public class ApiException(
    public val statusCode: Int,
    public val responseBody: String,
) : RuntimeException("Request failed: $statusCode $responseBody")
