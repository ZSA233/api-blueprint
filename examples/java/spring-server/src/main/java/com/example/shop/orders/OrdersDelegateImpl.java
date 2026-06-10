package com.example.shop.orders;

import com.example.shop.contract.api.routes.api.orders.adapters.GenOrdersAdapters;
import com.example.shop.contract.api.routes.api.orders.delegates.GenOrdersDelegate;
import com.example.shop.contract.api.routes.api.orders.types.GenOrdersTypes;
import com.example.shop.contract.api.spring.GenSpringRequestContext;
import org.springframework.stereotype.Service;

@Service
public class OrdersDelegateImpl implements GenOrdersDelegate {
    @Override
    public GenOrdersTypes.CreateOrderResponse createOrder(
        GenOrdersTypes.CreateOrderJSON request,
        GenSpringRequestContext context
    ) {
        GenOrdersTypes.CreateOrderResponse response = GenOrdersTypes.CreateOrderResponse.builder()
            .orderId("order-" + request.getSku())
            .status("created")
            .build();
        return GenOrdersAdapters.createOrderResponse(response);
    }
}
