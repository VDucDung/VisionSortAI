package com.example.hauiTrash.controller;

import com.example.hauiTrash.entity.*;
import com.example.hauiTrash.repository.AccountRepository;
import com.example.hauiTrash.service.ScanQueryService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import java.time.LocalDate;

@RestController
@RequestMapping("/api/v1/admin")
@PreAuthorize("hasRole('ADMIN')")
@RequiredArgsConstructor
public class AdminWorkspaceController {
    private final ScanQueryService queries;
    private final AccountRepository accounts;
    @GetMapping("/statistics")
    public ScanQueryService.Statistics statistics(@RequestParam(required = false) LocalDate from, @RequestParam(required = false) LocalDate to) {
        return queries.statistics(from, to);
    }
    @GetMapping("/scans")
    public ScanQueryService.PageResult<ScanQueryService.ScanSummary> scans(
        @RequestParam(defaultValue = "0") int page, @RequestParam(defaultValue = "12") int size,
        @RequestParam(required = false) String q, @RequestParam(required = false) String material,
        @RequestParam(required = false) LocalDate from, @RequestParam(required = false) LocalDate to) {
        return queries.history(true, page, size, q, material, from, to);
    }
    @GetMapping("/users")
    public ScanQueryService.PageResult<ScanQueryService.UserView> users(@RequestParam(defaultValue = "0") int page,
        @RequestParam(defaultValue = "12") int size, @RequestParam(required = false) String q) { return queries.users(page, size, q); }
    public record UserUpdate(@NotBlank @Size(max=120) String fullName, @NotBlank @Pattern(regexp="^0\\d{9,10}$") String phone,
        @Email @Size(max=120) String email, @NotNull Boolean active) {}
    @PatchMapping("/users/{id}")
    @Transactional
    public ScanQueryService.UserView update(@PathVariable Integer id, @Valid @RequestBody UserUpdate update) {
        Account user = accounts.findById(id).filter(a -> a.getRole() == AccountRole.USER)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Không tìm thấy người dùng"));
        accounts.findByPhone(update.phone()).filter(a -> !a.getId().equals(id)).ifPresent(a -> { throw new ResponseStatusException(HttpStatus.CONFLICT, "Số điện thoại đã được sử dụng"); });
        String email = update.email() == null || update.email().isBlank() ? null : update.email().trim();
        if (email != null) accounts.findByEmail(email).filter(a -> !a.getId().equals(id)).ifPresent(a -> { throw new ResponseStatusException(HttpStatus.CONFLICT, "Email đã được sử dụng"); });
        user.setFullName(update.fullName().trim()); user.setPhone(update.phone()); user.setEmail(email); user.setIsActive(update.active());
        return ScanQueryService.user(accounts.save(user));
    }
}
