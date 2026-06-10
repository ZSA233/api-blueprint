package com.example.shop;

import static org.assertj.core.api.Assertions.assertThat;

import com.example.shop.contract.api.spring.GenSpringMvcContractAssertions;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerMapping;

@SpringBootTest
class PublicApiContractTest {
    @Autowired
    private RequestMappingHandlerMapping mappings;

    @Test
    void publicApiMatchesBlueprint() {
        GenSpringMvcContractAssertions.ContractReport report = GenSpringMvcContractAssertions.assertMatches(mappings);
        assertThat(report.hasErrors()).isFalse();
    }
}
