package com.example.hauiTrash.repository;

import com.example.hauiTrash.entity.Account;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface AccountRepository extends JpaRepository<Account, Integer>, org.springframework.data.jpa.repository.JpaSpecificationExecutor<Account> {
    @org.springframework.data.jpa.repository.Lock(jakarta.persistence.LockModeType.PESSIMISTIC_WRITE)
    @org.springframework.data.jpa.repository.Query("select a from Account a where a.id = :id")
    Optional<Account> findByIdForUpdate(@org.springframework.data.repository.query.Param("id") Integer id);
    Optional<Account> findByPhone(String phone);
    Optional<Account> findByEmail(String email);
    Optional<Account> findByEmailIgnoreCase(String email);
    boolean existsByPhone(String phone);
    boolean existsByEmail(String email);
}
