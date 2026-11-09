package com.example.hauiTrash.controller;

import com.example.hauiTrash.dto.*;
import com.example.hauiTrash.service.AdminProfileService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/admin/profile")
@PreAuthorize("hasRole('ADMIN')")
@RequiredArgsConstructor
public class AdminProfileController {
    private final AdminProfileService profiles;
    public record ProfileUpdate(@NotBlank @Size(max=120) String fullName,
        @NotBlank @Pattern(regexp="^0\\d{9,10}$") String phone,
        @NotBlank @Email @Size(max=120) String email, @Size(max=72) String currentPassword) {
        @Override public String toString() { return "AdminProfileUpdate[credentials redacted]"; }
    }
    public record PasswordUpdate(@NotBlank @Size(max=72) String currentPassword,
        @NotBlank @Size(min=8,max=72,message="Mật khẩu mới cần từ 8 đến 72 ký tự") String newPassword) {
        @Override public String toString() { return "AdminPasswordUpdate[credentials redacted]"; }
    }
    @GetMapping public AccountInfo get() { return profiles.get(); }
    @PatchMapping public AuthResponse update(@Valid @RequestBody ProfileUpdate update) {
        return profiles.update(update.fullName(),update.phone(),update.email(),update.currentPassword());
    }
    @PostMapping("/password") public AuthResponse password(@Valid @RequestBody PasswordUpdate update) {
        return profiles.changePassword(update.currentPassword(),update.newPassword());
    }
}
