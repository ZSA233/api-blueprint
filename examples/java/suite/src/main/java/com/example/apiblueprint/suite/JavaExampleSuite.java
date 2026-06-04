package com.example.apiblueprint.suite;

import com.example.apiblueprint.api.adapters.api.demo.GenDemoAdapters;
import com.example.apiblueprint.api.annotations.ApiBlueprintOperation;
import com.example.apiblueprint.api.annotations.api.demo.GenDemoAbc;
import com.example.apiblueprint.api.runtime.GenApiTypes;
import com.example.apiblueprint.api.types.api.demo.GenDemoTypes;
import com.example.apiblueprint.security.SignatureRequired;
import java.util.List;

public final class JavaExampleSuite {
    private JavaExampleSuite() {
    }

    public static void main(String[] args) {
        ApiBlueprintOperation operation = GenDemoAbc.class.getAnnotation(ApiBlueprintOperation.class);
        require(operation != null, "GenDemoAbc must carry ApiBlueprintOperation");
        require("api.demo.get.abc".equals(operation.value()), "operation id mismatch: " + operation.value());
        require(GenDemoAbc.class.isAnnotationPresent(SignatureRequired.class), "policy annotation missing");

        GenDemoTypes.AbcQuery query = GenDemoTypes.AbcQuery.builder()
            .arg1(Boolean.TRUE)
            .arg2(2.5f)
            .arg3("suite")
            .build();
        require(Boolean.TRUE.equals(query.getArg1()), "query arg1 mismatch");
        require(Float.valueOf(2.5f).equals(query.getArg2()), "query arg2 mismatch");
        require("suite".equals(query.getArg3()), "query arg3 mismatch");
        require(GenDemoAdapters.abcRequest(query) == query, "request adapter should preserve generated type");

        GenApiTypes.ApiDemoA response = new GenApiTypes.ApiDemoA(
            "bc",
            7,
            1.5f,
            List.of(1L, 2L),
            List.of(),
            GenApiTypes.ColorEnum.RED,
            GenApiTypes.StatusEnum.RUNNING,
            List.of(GenApiTypes.StatusEnum.RUNNING)
        );
        require(GenDemoAdapters.abcResponse(response) == response, "response adapter should preserve generated type");
        System.out.println("java example suite passed");
    }

    private static void require(boolean condition, String message) {
        if (!condition) {
            throw new IllegalStateException(message);
        }
    }
}
