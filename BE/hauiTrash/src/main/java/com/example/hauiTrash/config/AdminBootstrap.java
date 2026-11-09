package com.example.hauiTrash.config;

import com.example.hauiTrash.entity.*;
import com.example.hauiTrash.repository.AccountRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

/** Explicit, one-time provisioning; there is no public admin registration route. */
@Component
@RequiredArgsConstructor
@lombok.extern.slf4j.Slf4j
public class AdminBootstrap implements ApplicationRunner {
    private final AccountRepository accounts;
    private final PasswordEncoder passwords;
    @Value("${app.admin.bootstrap-enabled:false}") private boolean enabled;
    @Value("${app.admin.email:}") private String email;
    @Value("${app.admin.password:}") private String password;
    @Value("${app.admin.phone:}") private String phone;
    @Value("${app.admin.update-existing:false}") private boolean updateExisting;
    @Override
    @Transactional
    public void run(ApplicationArguments args) {
        if (!enabled) {
            if (!email.isBlank() || !password.isBlank() || !phone.isBlank() || updateExisting)
                log.warn("Đã bỏ qua cấu hình cấp admin vì bước cấp tài khoản chưa được bật. BE tiếp tục khởi động bình thường; dùng create-admin.ps1 khi cần tạo/cập nhật admin.");
            return;
        }
        if (email.isBlank() && password.isBlank() && phone.isBlank() && !updateExisting) return;
        if (email.isBlank() || password.isBlank())
            throw new IllegalArgumentException("Cấp admin cần ADMIN_EMAIL và ADMIN_PASSWORD. Không có tài khoản nào được thay đổi.");
        String normalizedEmail = email.trim().toLowerCase(Locale.ROOT);
        String normalizedPhone = phone.trim();
        if (password.length() < 8 || password.getBytes(StandardCharsets.UTF_8).length > 72)
            throw new IllegalArgumentException("Mật khẩu admin cần ít nhất 8 ký tự và tối đa 72 byte UTF-8.");
        var existing = accounts.findByEmailIgnoreCase(normalizedEmail);
        if (existing.isPresent()) {
            Account account = existing.get();
            if (!normalizedPhone.isEmpty() && !normalizedPhone.equals(account.getPhone()))
                throw new IllegalStateException("Không thể cấp admin: email và số điện thoại không thuộc cùng một tài khoản. "
                    + "Để cập nhật đúng tài khoản theo email, bỏ ADMIN_PHONE và bật ADMIN_UPDATE_EXISTING=true; hoặc dùng email/số điện thoại mới.");
            if (!updateExisting) {
                if (account.getRole() == AccountRole.ADMIN) {
                    log.info("Tài khoản ADMIN đã tồn tại (id={}); mật khẩu không thay đổi. Muốn đặt lại mật khẩu cần ADMIN_UPDATE_EXISTING=true.", account.getId());
                    return;
                }
                throw new IllegalStateException("Email cấp admin đã thuộc tài khoản " + account.getRole()
                    + ". Chưa tạo admin và chưa đổi mật khẩu. Dùng email mới hoặc bật ADMIN_UPDATE_EXISTING=true để chuyển đúng tài khoản này thành ADMIN.");
            }
            if (!Boolean.TRUE.equals(account.getIsActive()))
                throw new IllegalStateException("Tài khoản được chọn đang bị khóa. Không cập nhật quyền hoặc mật khẩu của tài khoản bị khóa.");
            account.setRole(AccountRole.ADMIN);
            account.setPasswordHash(passwords.encode(password));
            account.setTokenVersion(account.getTokenVersion() + 1);
            accounts.save(account);
            log.info("Đã cập nhật tài khoản được chọn thành ADMIN và đặt mật khẩu theo cấu hình (id={}); thông tin và lịch sử được giữ nguyên.", account.getId());
            return;
        }
        if (!normalizedPhone.matches("^0\\d{9,10}$"))
            throw new IllegalArgumentException("Tạo admin mới cần ADMIN_PHONE bắt đầu bằng 0, có 10–11 chữ số.");
        if (accounts.existsByPhone(normalizedPhone))
            throw new IllegalStateException("Số điện thoại cấp admin đã được tài khoản khác sử dụng. Chưa tạo tài khoản; hãy dùng số mới.");
        Account created = accounts.save(Account.builder().email(normalizedEmail).phone(normalizedPhone).fullName("Quản trị viên")
            .passwordHash(passwords.encode(password)).role(AccountRole.ADMIN).isActive(true).build());
        log.info("Đã tạo tài khoản ADMIN mới (id={}).", created.getId());
    }
}
