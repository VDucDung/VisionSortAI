package com.example.hauiTrash.service;

import java.util.Locale;
import java.util.Map;

/** Stable material codes shared with the ResNet checkpoint. Never infer new labels with an LLM. */
public final class MaterialCatalog {
    public record Material(String code, String name, String color, String guidance) {}
    public static final Map<String, Material> ALL = Map.of(
        "glass", new Material("glass", "Thủy tinh", "#5586a8", "Tách riêng thủy tinh, làm rỗng và rửa sạch. Bọc kín mảnh vỡ, ghi chú để người thu gom nhận biết."),
        "metal", new Material("metal", "Kim loại", "#718096", "Làm rỗng và rửa sạch lon, hộp kim loại. Để khô, thu gom riêng và chuyển đến điểm tiếp nhận tái chế."),
        "paper", new Material("paper", "Giấy", "#c28b46", "Giữ giấy sạch và khô, gấp gọn trước khi thu gom. Tách riêng giấy dính dầu, thức ăn hoặc hóa chất."),
        "plastic", new Material("plastic", "Nhựa", "#278566", "Làm rỗng, rửa sạch và để khô. Kiểm tra ký hiệu nhựa và quy định tiếp nhận của điểm thu gom địa phương.")
    );
    private MaterialCatalog() {}
    public static Material find(String label) {
        return label == null ? null : ALL.get(label.toLowerCase(Locale.ROOT).trim());
    }
}
