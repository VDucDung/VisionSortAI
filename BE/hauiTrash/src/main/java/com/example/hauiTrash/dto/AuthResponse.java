package com.example.hauiTrash.dto;

import lombok.Builder;
import lombok.Data;

@Data
@Builder
public class AuthResponse {
    @lombok.ToString.Exclude
    private String token;
    private String tokenType;
    private long expiresIn;
    private AccountInfo account;
}
