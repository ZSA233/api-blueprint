plugins {
    java
    id("org.springframework.boot") version "3.3.6"
    id("io.spring.dependency-management") version "1.1.6"
}

dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

sourceSets {
    main {
        java.srcDir("generated")
    }
    create("benchmark") {
        java.srcDir("src/benchmark/java")
        compileClasspath += sourceSets["main"].output + configurations["testRuntimeClasspath"]
        runtimeClasspath += output + compileClasspath
    }
}

tasks.test {
    useJUnitPlatform()
}

tasks.register<JavaExec>("benchmark") {
    group = "verification"
    description = "Run opt-in Java Spring controller/delegate microbenchmarks."
    classpath = sourceSets["benchmark"].runtimeClasspath
    mainClass.set("com.example.shop.benchmark.JavaSpringServerContractBenchmark")
    args(
        "--iterations=${project.findProperty("benchmarkIterations") ?: "200000"}",
        "--warmup=${project.findProperty("benchmarkWarmup") ?: "20000"}",
        "--contract-iterations=${project.findProperty("benchmarkContractIterations") ?: "1000"}",
        "--contract-warmup=${project.findProperty("benchmarkContractWarmup") ?: "20"}",
    )
}
