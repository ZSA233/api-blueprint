package com.example.apiblueprint.internal

import java.net.URLEncoder

internal fun buildUrl(baseUrl: String, path: String, query: Map<String, String?> = emptyMap()): String {
    val normalizedBase = baseUrl.trimEnd('/')
    val normalizedPath = if (path.startsWith('/')) path else "/$path"
    val base = if (normalizedBase.isEmpty()) normalizedPath else normalizedBase + normalizedPath
    val queryString = query.entries
        .filter { it.value != null }
        .joinToString("&") { (key, value) ->
            encode(key) + "=" + encode(value ?: "")
        }
    return if (queryString.isEmpty()) base else "$base?$queryString"
}

private fun encode(value: String): String = URLEncoder.encode(value, Charsets.UTF_8.name())
