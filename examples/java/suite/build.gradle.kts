plugins {
    java
    application
}

dependencies {
    implementation("com.fasterxml.jackson.core:jackson-databind:2.17.2")
    implementation("org.springframework.boot:spring-boot-starter-web:3.3.6")
}

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

val generatedSourcesDir = layout.buildDirectory.dir("generated/sources/apiBlueprintJavaSuite/java")

val cleanGeneratedJavaExamples = tasks.register<Delete>("cleanGeneratedJavaExamples") {
    delete(generatedSourcesDir)
}

val copyGeneratedJavaClient = tasks.register<Copy>("copyGeneratedJavaClient") {
    dependsOn(cleanGeneratedJavaExamples)
    from(layout.projectDirectory.dir("../client/com"))
    into(generatedSourcesDir.map { it.dir("com") })
}

val copyGeneratedJavaServer = tasks.register<Copy>("copyGeneratedJavaServer") {
    dependsOn(copyGeneratedJavaClient)
    from(layout.projectDirectory.dir("../server/com"))
    into(generatedSourcesDir.map { it.dir("com") })
}

sourceSets {
    main {
        java.srcDir(generatedSourcesDir)
    }
}

tasks.named<JavaCompile>("compileJava") {
    dependsOn(copyGeneratedJavaServer)
    options.encoding = "UTF-8"
}

tasks.named<JavaExec>("run") {
    jvmArgs("--enable-native-access=ALL-UNNAMED")
}

application {
    mainClass.set("com.example.apiblueprint.suite.JavaExampleSuite")
}
