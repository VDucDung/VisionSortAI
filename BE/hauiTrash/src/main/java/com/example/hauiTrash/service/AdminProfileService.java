package com.example.hauiTrash.service;

import com.example.hauiTrash.dto.*;
import com.example.hauiTrash.entity.*;
import com.example.hauiTrash.exception.*;
import com.example.hauiTrash.repository.AccountRepository;
import com.example.hauiTrash.security.*;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

@Service
@RequiredArgsConstructor
@Transactional
public class AdminProfileService {
    private final AccountRepository accounts;
    private final CurrentAccount current;
    private final PasswordEncoder passwords;
    private final JwtUtil jwt;

    public AccountInfo get() { return info(selected()); }

    public AuthResponse update(String fullName, String phone, String email, String currentPassword) {
        Account account=selected();
        String normalizedEmail=email.trim().toLowerCase(Locale.ROOT);
        boolean emailChanged=account.getEmail()==null || !normalizedEmail.equalsIgnoreCase(account.getEmail());
        if(emailChanged) verifyPassword(account,currentPassword);
        accounts.findByPhone(phone).filter(other->!other.getId().equals(account.getId())).ifPresent(other->{
            throw new ResponseStatusException(HttpStatus.CONFLICT,"Số điện thoại đã được sử dụng");
        });
        accounts.findByEmailIgnoreCase(normalizedEmail).filter(other->!other.getId().equals(account.getId())).ifPresent(other->{
            throw new ResponseStatusException(HttpStatus.CONFLICT,"Email đã được sử dụng");
        });
        account.setFullName(fullName.trim());account.setPhone(phone);account.setEmail(normalizedEmail);
        if(emailChanged) account.setTokenVersion(account.getTokenVersion()+1);
        accounts.saveAndFlush(account);
        return authenticated(account);
    }

    public AuthResponse changePassword(String currentPassword,String newPassword) {
        Account account=selected();verifyPassword(account,currentPassword);
        if(newPassword.getBytes(StandardCharsets.UTF_8).length>72)
            throw new BadRequestException("Mật khẩu mới tối đa 72 byte UTF-8");
        if(passwords.matches(newPassword,account.getPasswordHash()))
            throw new BadRequestException("Mật khẩu mới cần khác mật khẩu hiện tại");
        account.setPasswordHash(passwords.encode(newPassword));
        account.setTokenVersion(account.getTokenVersion()+1);
        accounts.saveAndFlush(account);
        return authenticated(account);
    }

    private Account selected() {
        Account principal=current.get();
        Account account=accounts.findByIdForUpdate(principal.getId())
            .orElseThrow(()->new UnauthorizedException("Tài khoản không còn tồn tại"));
        if(account.getRole()!=AccountRole.ADMIN) throw new ForbiddenException("Chỉ quản trị viên được sử dụng chức năng này");
        if(!Boolean.TRUE.equals(account.getIsActive()) || account.getTokenVersion()!=principal.getTokenVersion())
            throw new UnauthorizedException("Phiên đăng nhập không còn hợp lệ. Vui lòng đăng nhập lại.");
        return account;
    }
    private void verifyPassword(Account account,String candidate) {
        if(candidate==null || candidate.isBlank() || candidate.getBytes(StandardCharsets.UTF_8).length>72
            || !passwords.matches(candidate,account.getPasswordHash()))
            throw new BadRequestException("Mật khẩu hiện tại không đúng");
    }
    private AccountInfo info(Account a) {
        return AccountInfo.builder().id(a.getId()).fullName(a.getFullName()).phone(a.getPhone()).email(a.getEmail()).role(a.getRole().name()).build();
    }
    private AuthResponse authenticated(Account a) {
        return AuthResponse.builder().token(jwt.generateToken(a.getId(),a.getRole(),a.getTokenVersion()))
            .tokenType("Bearer").expiresIn(jwt.getExpirationSeconds()).account(info(a)).build();
    }
}
