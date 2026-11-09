package com.example.hauiTrash;

import com.example.hauiTrash.entity.*;
import com.example.hauiTrash.repository.AccountRepository;
import com.example.hauiTrash.security.JwtUtil;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties="spring.datasource.url=jdbc:h2:mem:adminprofile;MODE=MySQL;DB_CLOSE_DELAY=-1")
@AutoConfigureMockMvc
@ActiveProfiles("test")
class AdminProfileIntegrationTest {
    @Autowired MockMvc mvc;
    @Autowired AccountRepository accounts;
    @Autowired PasswordEncoder encoder;
    @Autowired JwtUtil jwt;
    @Autowired ObjectMapper json;
    static final AtomicInteger numbers=new AtomicInteger(3_000_000);
    static final String PASSWORD="Original-pass-2026!";
    Account admin,other,user;
    @BeforeEach void setup(){admin=create(AccountRole.ADMIN);other=create(AccountRole.ADMIN);user=create(AccountRole.USER);}
    Account create(AccountRole role) {
        int n=numbers.incrementAndGet();
        return accounts.save(Account.builder().phone("090"+n).email("profile"+n+"@example.com").fullName("Account "+n)
            .role(role).isActive(true).passwordHash(encoder.encode(PASSWORD)).build());
    }
    String token(Account account){return "Bearer "+jwt.generateToken(account.getId(),account.getRole(),account.getTokenVersion());}
    @Test void onlyAdminsCanReadAndEditTheirProfile() throws Exception {
        mvc.perform(get("/api/v1/admin/profile")).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/v1/admin/profile").header("Authorization",token(user))).andExpect(status().isForbidden());
        mvc.perform(get("/api/v1/admin/profile").header("Authorization",token(admin))).andExpect(status().isOk())
            .andExpect(jsonPath("id").value(admin.getId())).andExpect(jsonPath("role").value("ADMIN"))
            .andExpect(jsonPath("passwordHash").doesNotExist()).andExpect(jsonPath("tokenVersion").doesNotExist());
        mvc.perform(patch("/api/v1/admin/profile").header("Authorization",token(user)).contentType(MediaType.APPLICATION_JSON)
            .content(json.writeValueAsString(Map.of("fullName","Other","phone",user.getPhone(),"email",user.getEmail())))).andExpect(status().isForbidden());
    }
    @Test void ownProfileCanBeUpdatedAndForgedIdsRolesAreIgnored() throws Exception {
        mvc.perform(patch("/api/v1/admin/profile").header("Authorization",token(admin)).contentType(MediaType.APPLICATION_JSON)
            .content(json.writeValueAsString(Map.of("id",other.getId(),"role","USER","active",false,"fullName","New name","phone",admin.getPhone(),"email",admin.getEmail()))))
            .andExpect(status().isOk()).andExpect(jsonPath("account.id").value(admin.getId())).andExpect(jsonPath("account.fullName").value("New name"))
            .andExpect(jsonPath("account.role").value("ADMIN")).andExpect(jsonPath("token").isString());
        assertEquals(other.getFullName(),accounts.findById(other.getId()).orElseThrow().getFullName());
        assertTrue(accounts.findById(admin.getId()).orElseThrow().getIsActive());
    }
    @Test void changingEmailRequiresCurrentPasswordAndNormalizesNewLogin() throws Exception {
        String oldToken=token(admin),email="new"+admin.getId()+"@example.com";
        var body=Map.of("fullName",admin.getFullName(),"phone",admin.getPhone(),"email",email,"currentPassword","incorrect");
        mvc.perform(patch("/api/v1/admin/profile").header("Authorization",oldToken).contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(body)))
            .andExpect(status().isBadRequest());
        assertEquals(admin.getEmail(),accounts.findById(admin.getId()).orElseThrow().getEmail());
        var result=mvc.perform(patch("/api/v1/admin/profile").header("Authorization",oldToken).contentType(MediaType.APPLICATION_JSON)
            .content(json.writeValueAsString(Map.of("fullName",admin.getFullName(),"phone",admin.getPhone(),"email",email.toUpperCase(),"currentPassword",PASSWORD))))
            .andExpect(status().isOk()).andExpect(jsonPath("account.email").value(email)).andReturn();
        String replacement=json.readTree(result.getResponse().getContentAsString()).get("token").asText();
        mvc.perform(get("/api/v1/admin/profile").header("Authorization",oldToken)).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/v1/admin/profile").header("Authorization","Bearer "+replacement)).andExpect(status().isOk());
        mvc.perform(post("/api/v1/auth/login/admin").contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(Map.of("identifier",email,"password",PASSWORD))))
            .andExpect(status().isOk()).andExpect(jsonPath("data.account.id").value(admin.getId()));
    }
    @Test void duplicateEmailsAndPhonesAreRejectedWithoutChanges() throws Exception {
        mvc.perform(patch("/api/v1/admin/profile").header("Authorization",token(admin)).contentType(MediaType.APPLICATION_JSON)
            .content(json.writeValueAsString(Map.of("fullName","New name","phone",other.getPhone(),"email",admin.getEmail())))).andExpect(status().isConflict());
        mvc.perform(patch("/api/v1/admin/profile").header("Authorization",token(admin)).contentType(MediaType.APPLICATION_JSON)
            .content(json.writeValueAsString(Map.of("fullName","New name","phone",admin.getPhone(),"email",other.getEmail(),"currentPassword",PASSWORD)))).andExpect(status().isConflict());
        assertEquals(admin.getFullName(),accounts.findById(admin.getId()).orElseThrow().getFullName());
    }
    @Test void passwordChangeRequiresOldPasswordAndRevokesPreviousTokens() throws Exception {
        String oldToken=token(admin),next="New-password-2026!";
        mvc.perform(post("/api/v1/admin/profile/password").header("Authorization",oldToken).contentType(MediaType.APPLICATION_JSON)
            .content(json.writeValueAsString(Map.of("currentPassword","wrong","newPassword",next)))).andExpect(status().isBadRequest());
        mvc.perform(get("/api/v1/admin/profile").header("Authorization",oldToken)).andExpect(status().isOk());
        var result=mvc.perform(post("/api/v1/admin/profile/password").header("Authorization",oldToken).contentType(MediaType.APPLICATION_JSON)
            .content(json.writeValueAsString(Map.of("currentPassword",PASSWORD,"newPassword",next)))).andExpect(status().isOk()).andReturn();
        String replacement=json.readTree(result.getResponse().getContentAsString()).get("token").asText();
        mvc.perform(get("/api/v1/admin/profile").header("Authorization",oldToken)).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/v1/admin/profile").header("Authorization","Bearer "+replacement)).andExpect(status().isOk());
        mvc.perform(post("/api/v1/auth/login/admin").contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(Map.of("identifier",admin.getEmail(),"password",PASSWORD))))
            .andExpect(status().isUnauthorized());
        mvc.perform(post("/api/v1/auth/login/admin").contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(Map.of("identifier",admin.getEmail(),"password",next))))
            .andExpect(status().isOk());
        assertTrue(encoder.matches(next,accounts.findById(admin.getId()).orElseThrow().getPasswordHash()));
        assertTrue(encoder.matches(PASSWORD,accounts.findById(other.getId()).orElseThrow().getPasswordHash()));
    }
    @Test void invalidProfileAndWeakOrUnchangedPasswordDoNotInvalidateSession() throws Exception {
        mvc.perform(patch("/api/v1/admin/profile").header("Authorization",token(admin)).contentType(MediaType.APPLICATION_JSON)
            .content("{\"fullName\":\"\",\"phone\":\"invalid\",\"email\":\"invalid\"}")).andExpect(status().isBadRequest());
        for(String next:new String[]{"short",PASSWORD,"界".repeat(30)}) {
            mvc.perform(post("/api/v1/admin/profile/password").header("Authorization",token(admin)).contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("currentPassword",PASSWORD,"newPassword",next)))).andExpect(status().isBadRequest());
        }
        mvc.perform(get("/api/v1/admin/profile").header("Authorization",token(admin))).andExpect(status().isOk());
    }
    @Test void passwordAndTokenValuesAreRedactedFromLogRepresentations() {
        var profile=new com.example.hauiTrash.controller.AdminProfileController.ProfileUpdate("Name","0912345678","admin@example.com","private-old-password");
        var change=new com.example.hauiTrash.controller.AdminProfileController.PasswordUpdate("private-old-password","private-new-password");
        var response=com.example.hauiTrash.dto.AuthResponse.builder().token("private-jwt-value").build();
        var login=new com.example.hauiTrash.dto.LoginRequest();login.setPassword("private-old-password");
        assertFalse(profile.toString().contains("private-old-password"));assertFalse(change.toString().contains("private-old-password"));
        assertFalse(change.toString().contains("private-new-password"));assertFalse(response.toString().contains("private-jwt-value"));
        assertFalse(login.toString().contains("private-old-password"));
    }
}
