package com.proofly.backend.api.dto;

import com.proofly.backend.domain.Product;
import java.util.UUID;

public record ProductDto(
        UUID id,
        String rawQuery,
        String canonicalName,
        String brand,
        String category,
        String model) {

    public static ProductDto from(Product product) {
        if (product == null) {
            return null;
        }
        return new ProductDto(product.getId(), product.getRawQuery(), product.getCanonicalName(),
                product.getBrand(), product.getCategory(), product.getModel());
    }
}
