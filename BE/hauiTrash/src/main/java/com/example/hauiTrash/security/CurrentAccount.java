package com.example.hauiTrash.security;

import com.example.hauiTrash.entity.*;
import com.example.hauiTrash.exception.*;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import java.util.Objects;

@Component
public class CurrentAccount {
    public Account get() {
        var authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null || !(authentication.getPrincipal() instanceof Account account))
            throw new UnauthorizedException("Bạn cần đăng nhập để tiếp tục");
        return account;
    }
    public void checkOwner(AiRequest request) {
        var account = get();
        if (account.getRole() != AccountRole.ADMIN &&
            (request.getAccount() == null || !Objects.equals(account.getId(), request.getAccount().getId())))
            throw new ForbiddenException("Bạn không có quyền truy cập lượt quét này");
    }
}
