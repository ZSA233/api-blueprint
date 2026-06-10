package com.example.shop.benchmark;

import com.example.shop.contract.api.annotations.ApiBlueprintOperation;
import com.example.shop.contract.api.routes.api.orders.adapters.GenOrdersAdapters;
import com.example.shop.contract.api.routes.api.orders.controllers.GenOrdersController;
import com.example.shop.contract.api.routes.api.orders.types.GenOrdersTypes;
import com.example.shop.contract.api.runtime.GenApiResponseEnvelope;
import com.example.shop.contract.api.spring.GenSpringMvcContractAssertions;
import com.example.shop.contract.api.spring.GenSpringMvcContractAssertions.ContractMode;
import com.example.shop.contract.api.spring.GenSpringResponseWriter;
import com.example.shop.orders.OrdersDelegateImpl;
import com.example.shop.security.SignatureRequired;
import jakarta.servlet.http.HttpServletRequest;
import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.Map;
import org.springframework.core.annotation.AnnotatedElementUtils;
import org.springframework.mock.web.MockServletContext;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.context.support.StaticWebApplicationContext;
import org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerMapping;

public final class JavaSpringServerContractBenchmark {
    private static volatile Object sink;

    private JavaSpringServerContractBenchmark() {
    }

    public static void main(String[] args) throws Exception {
        Options options = Options.parse(args);
        GenOrdersTypes.CreateOrderJSON request = GenOrdersTypes.CreateOrderJSON.builder()
            .sku("sku-123")
            .quantity(2)
            .note("benchmark")
            .build();

        GenOrdersController generatedController = new GenOrdersController(new OrdersDelegateImpl());
        PlainSpringStyleController plainController = new PlainSpringStyleController();
        Method generatedMethod = GenOrdersController.class.getMethod(
            "createOrder",
            GenOrdersTypes.CreateOrderJSON.class,
            HttpServletRequest.class
        );
        Method plainMethod = PlainSpringStyleController.class.getMethod(
            "createOrder",
            GenOrdersTypes.CreateOrderJSON.class,
            HttpServletRequest.class
        );

        assertSanity(generatedController, plainController, request, generatedMethod, plainMethod);

        System.out.println("java-spring-controller-delegate benchmark");
        System.out.println("iterations=" + options.iterations + " warmup=" + options.warmup);

        Result generatedHandler = benchmark(
            "handler.generated-controller-delegate",
            options.warmup,
            options.iterations,
            () -> sink = generatedController.createOrder(request, null).getBody()
        );
        Result plainHandler = benchmark(
            "handler.plain-spring-annotation",
            options.warmup,
            options.iterations,
            () -> sink = plainController.createOrder(request, null).getBody()
        );
        compare("handler.generated_vs_plain", generatedHandler, plainHandler);

        Result generatedLookup = benchmark(
            "annotation-lookup.generated-meta",
            options.warmup,
            options.iterations,
            () -> {
                sink = AnnotatedElementUtils.hasAnnotation(generatedMethod, SignatureRequired.class);
                sink = AnnotatedElementUtils.findMergedAnnotation(generatedMethod, ApiBlueprintOperation.class);
            }
        );
        Result plainLookup = benchmark(
            "annotation-lookup.plain-direct",
            options.warmup,
            options.iterations,
            () -> {
                sink = AnnotatedElementUtils.hasAnnotation(plainMethod, SignatureRequired.class);
                sink = AnnotatedElementUtils.findMergedAnnotation(plainMethod, ApiBlueprintOperation.class);
            }
        );
        compare("annotation-lookup.generated_vs_plain", generatedLookup, plainLookup);

        try (StaticWebApplicationContext context = new StaticWebApplicationContext()) {
            context.setServletContext(new MockServletContext());
            context.registerBean(OrdersDelegateImpl.class);
            context.registerBean(GenOrdersController.class);
            context.refresh();
            RequestMappingHandlerMapping mappings = new RequestMappingHandlerMapping();
            mappings.setApplicationContext(context);
            mappings.afterPropertiesSet();
            System.out.println(
                "contract_iterations=" + options.contractIterations
                    + " contract_warmup=" + options.contractWarmup
            );
            benchmark(
                "contract-assertion.inspect",
                options.contractWarmup,
                options.contractIterations,
                () -> sink = GenSpringMvcContractAssertions.inspect(mappings, ContractMode.PUBLIC).hasErrors()
            );
        }
    }

    private static void assertSanity(
        GenOrdersController generatedController,
        PlainSpringStyleController plainController,
        GenOrdersTypes.CreateOrderJSON request,
        Method generatedMethod,
        Method plainMethod
    ) throws Exception {
        Object generatedBody = generatedController.createOrder(request, null).getBody();
        Object plainBody = plainController.createOrder(request, null).getBody();
        String generatedId = "";
        if (generatedBody instanceof Map<?, ?> envelope
            && envelope.get("data") instanceof GenOrdersTypes.CreateOrderResponse generatedResponse) {
            generatedId = generatedResponse.getOrderId();
        }
        String plainId = "";
        if (plainBody instanceof Map<?, ?> envelope
            && envelope.get("data") instanceof GenOrdersTypes.CreateOrderResponse plainResponse) {
            plainId = plainResponse.getOrderId();
        }
        if (!plainId.equals(generatedId)) {
            throw new IllegalStateException("handler baselines are not equivalent");
        }
        if (!AnnotatedElementUtils.hasAnnotation(generatedMethod, SignatureRequired.class)) {
            throw new IllegalStateException("generated controller method does not expose SignatureRequired");
        }
        if (!AnnotatedElementUtils.hasAnnotation(plainMethod, SignatureRequired.class)) {
            throw new IllegalStateException("plain controller method does not expose SignatureRequired");
        }
        ApiBlueprintOperation operation = AnnotatedElementUtils.findMergedAnnotation(
            generatedMethod,
            ApiBlueprintOperation.class
        );
        if (operation == null || !"api.orders.post.create".equals(operation.value())) {
            throw new IllegalStateException("generated controller method does not expose ApiBlueprintOperation");
        }
    }

    private static Result benchmark(String scenario, int warmup, int iterations, CheckedRunnable runnable)
        throws Exception {
        for (int index = 0; index < warmup; index++) {
            runnable.run();
        }
        long started = System.nanoTime();
        for (int index = 0; index < iterations; index++) {
            runnable.run();
        }
        long elapsed = System.nanoTime() - started;
        Result result = new Result(scenario, iterations, elapsed);
        System.out.printf(
            "scenario=%s iterations=%d elapsed_ns=%d ns_per_op=%.1f%n",
            result.scenario(),
            result.iterations(),
            result.elapsedNs(),
            result.nsPerOp()
        );
        return result;
    }

    private static void compare(String scenario, Result current, Result baseline) {
        double ratio = current.nsPerOp() / baseline.nsPerOp();
        System.out.printf(
            "scenario=%s current_ns_per_op=%.1f baseline_ns_per_op=%.1f ratio=%.3f%n",
            scenario,
            current.nsPerOp(),
            baseline.nsPerOp(),
            ratio
        );
    }

    @FunctionalInterface
    private interface CheckedRunnable {
        void run() throws Exception;
    }

    private record Result(String scenario, int iterations, long elapsedNs) {
        double nsPerOp() {
            return (double) elapsedNs / (double) iterations;
        }
    }

    private record Options(int iterations, int warmup, int contractIterations, int contractWarmup) {
        static Options parse(String[] args) {
            int iterations = 200_000;
            int warmup = 20_000;
            int contractIterations = 1_000;
            int contractWarmup = 20;
            for (String arg : args) {
                if (arg.startsWith("--iterations=")) {
                    iterations = positiveInt(arg, "--iterations=");
                } else if (arg.startsWith("--warmup=")) {
                    warmup = positiveInt(arg, "--warmup=");
                } else if (arg.startsWith("--contract-iterations=")) {
                    contractIterations = positiveInt(arg, "--contract-iterations=");
                } else if (arg.startsWith("--contract-warmup=")) {
                    contractWarmup = positiveInt(arg, "--contract-warmup=");
                } else {
                    throw new IllegalArgumentException(
                        "unknown benchmark argument: " + arg + "; args=" + Arrays.toString(args)
                    );
                }
            }
            return new Options(iterations, warmup, contractIterations, contractWarmup);
        }

        private static int positiveInt(String arg, String prefix) {
            int value = Integer.parseInt(arg.substring(prefix.length()));
            if (value <= 0) {
                throw new IllegalArgumentException(prefix + " must be positive");
            }
            return value;
        }
    }

    private static final class PlainSpringStyleController {
        @PostMapping("/api/orders/create")
        @SignatureRequired
        @ApiBlueprintOperation("api.orders.post.create")
        public ResponseEntity<?> createOrder(
            @RequestBody GenOrdersTypes.CreateOrderJSON request,
            HttpServletRequest servletRequest
        ) {
            GenOrdersTypes.CreateOrderResponse response = GenOrdersTypes.CreateOrderResponse.builder()
                .orderId("order-" + request.getSku())
                .status("created")
                .build();
            return GenSpringResponseWriter.response(
                GenOrdersAdapters.createOrderResponse(response),
                GenApiResponseEnvelope.of(
                    "CodeMessageDataEnvelope",
                    "code_message_data",
                    "nested",
                    0,
                    "ok",
                    new GenApiResponseEnvelope.Fields("code", "message", "data", "error", "ok")
                ),
                "application/json",
                "json"
            );
        }
    }
}
