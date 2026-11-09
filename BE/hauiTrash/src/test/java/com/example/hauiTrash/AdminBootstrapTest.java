package com.example.hauiTrash;

import com.example.hauiTrash.config.AdminBootstrap;
import com.example.hauiTrash.entity.*;
import com.example.hauiTrash.repository.AccountRepository;
import org.junit.jupiter.api.*;
import org.mockito.ArgumentCaptor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.util.ReflectionTestUtils;
import java.util.Optional;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class AdminBootstrapTest {
    AccountRepository accounts;
    PasswordEncoder passwords;
    AdminBootstrap bootstrap;
    @BeforeEach void setup() {
        accounts=mock(AccountRepository.class);passwords=mock(PasswordEncoder.class);
        bootstrap=new AdminBootstrap(accounts,passwords);
        ReflectionTestUtils.setField(bootstrap,"enabled",true);
        configure("admin@example.com","0912345678","New-password-2026",false);
        when(passwords.encode(anyString())).thenReturn("encoded-new-password");
        when(accounts.save(any())).thenAnswer(invocation->invocation.getArgument(0));
    }
    void configure(String email,String phone,String password,boolean update) {
        ReflectionTestUtils.setField(bootstrap,"email",email);ReflectionTestUtils.setField(bootstrap,"phone",phone);
        ReflectionTestUtils.setField(bootstrap,"password",password);ReflectionTestUtils.setField(bootstrap,"updateExisting",update);
    }
    Account existing(AccountRole role) {
        return Account.builder().id(7).email("admin@example.com").phone("0912345678")
            .role(role).passwordHash("original-password-hash").fullName("Original name").isActive(true).build();
    }
    @Test void noConfigurationHasNoSideEffects() {
        configure("","","",false);bootstrap.run(null);verifyNoInteractions(accounts,passwords);
    }
    @Test void normalStartupIgnoresStaleProvisioningSettingsWithoutChangingAccounts() {
        configure("old@example.com","invalid-phone","old-password",true);
        ReflectionTestUtils.setField(bootstrap,"enabled",false);
        bootstrap.run(null);
        verifyNoInteractions(accounts,passwords);
    }
    @Test void incompleteConfigurationFailsClearly() {
        configure("admin@example.com","0912345678","",false);
        assertThrows(IllegalArgumentException.class,()->bootstrap.run(null));verifyNoInteractions(accounts,passwords);
    }
    @Test void newAdminIsCreatedWithNormalizedEmailAndEncodedPassword() {
        configure(" ADMIN@EXAMPLE.COM ","0912345678","New-password-2026",false);
        bootstrap.run(null);var saved=ArgumentCaptor.forClass(Account.class);verify(accounts).save(saved.capture());
        assertEquals(AccountRole.ADMIN,saved.getValue().getRole());assertEquals("admin@example.com",saved.getValue().getEmail());
        assertEquals("encoded-new-password",saved.getValue().getPasswordHash());
    }
    @Test void existingUserIsNotSilentlySkippedOrPromoted() {
        var account=existing(AccountRole.USER);when(accounts.findByEmailIgnoreCase(anyString())).thenReturn(Optional.of(account));
        var error=assertThrows(IllegalStateException.class,()->bootstrap.run(null));
        assertTrue(error.getMessage().contains("ADMIN_UPDATE_EXISTING"));assertEquals(AccountRole.USER,account.getRole());
        verify(accounts,never()).save(any());verifyNoInteractions(passwords);
    }
    @Test void emailAndPhoneFromDifferentAccountsCannotBeCombined() {
        var account=existing(AccountRole.USER);when(accounts.findByEmailIgnoreCase(anyString())).thenReturn(Optional.of(account));
        configure("admin@example.com","0987654321","New-password-2026",true);
        assertThrows(IllegalStateException.class,()->bootstrap.run(null));assertEquals(AccountRole.USER,account.getRole());
        verify(accounts,never()).save(any());verifyNoInteractions(passwords);
    }
    @Test void explicitUpdateTargetsEmailAndPreservesOtherAccountInformation() {
        var account=existing(AccountRole.USER);when(accounts.findByEmailIgnoreCase(anyString())).thenReturn(Optional.of(account));
        configure("admin@example.com","","New-password-2026",true);bootstrap.run(null);
        assertEquals(AccountRole.ADMIN,account.getRole());assertEquals("encoded-new-password",account.getPasswordHash());
        assertEquals(7,account.getId());assertEquals("0912345678",account.getPhone());assertEquals("Original name",account.getFullName());
        verify(accounts).save(account);
    }
    @Test void existingAdminPasswordIsPreservedWithoutExplicitUpdate() {
        var account=existing(AccountRole.ADMIN);when(accounts.findByEmailIgnoreCase(anyString())).thenReturn(Optional.of(account));
        bootstrap.run(null);assertEquals("original-password-hash",account.getPasswordHash());verify(accounts,never()).save(any());verifyNoInteractions(passwords);
    }
    @Test void lockedAccountCannotBeReactivatedByBootstrap() {
        var account=existing(AccountRole.USER);account.setIsActive(false);when(accounts.findByEmailIgnoreCase(anyString())).thenReturn(Optional.of(account));
        configure("admin@example.com","","New-password-2026",true);assertThrows(IllegalStateException.class,()->bootstrap.run(null));
        assertFalse(account.getIsActive());verify(accounts,never()).save(any());verifyNoInteractions(passwords);
    }
    @Test void phoneConflictDoesNotCreateAnotherAccount() {
        when(accounts.existsByPhone("0912345678")).thenReturn(true);
        assertThrows(IllegalStateException.class,()->bootstrap.run(null));verify(accounts,never()).save(any());verifyNoInteractions(passwords);
    }
}
