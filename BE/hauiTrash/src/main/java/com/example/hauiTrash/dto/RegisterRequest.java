package com.example.hauiTrash.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class RegisterRequest {
    @NotBlank
    @jakarta.validation.constraints.Pattern(regexp = "^0\\d{9,10}$", message = "Số điện thoại cần có 10–11 chữ số và bắt đầu bằng 0")
    private String phone;

    @NotBlank
    @jakarta.validation.constraints.Size(min = 8, max = 72, message = "Mật khẩu cần từ 8 đến 72 ký tự")
    @lombok.ToString.Exclude
    private String password;

    @NotBlank
    @jakarta.validation.constraints.Size(max = 120)
    private String fullName;
}
