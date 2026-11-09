package com.example.hauiTrash;

import com.example.hauiTrash.entity.AccountRole;
import com.example.hauiTrash.repository.AccountRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.test.context.ActiveProfiles;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT,properties={
    "spring.datasource.url=jdbc:h2:mem:staleadmin;MODE=MySQL;DB_CLOSE_DELAY=-1",
    "spring.sql.init.mode=always", "spring.sql.init.data-locations=classpath:stale-admin-settings.sql",
    "spring.jpa.defer-datasource-initialization=true",
    "app.admin.bootstrap-enabled=false", "app.admin.email=old-user@example.com",
    "app.admin.phone=0901234568", "app.admin.password=Unused-old-password", "app.admin.update-existing=true"
})
@ActiveProfiles("test")
class NormalStartupAdminSettingsTest {
    @Autowired TestRestTemplate http;
    @Autowired AccountRepository accounts;
    @Test void conflictingOldAdminSettingsDoNotPreventNormalStartupOrAlterAccounts() {
        var response=http.getForEntity("/api/v1/system/info",String.class);
        assertEquals(200,response.getStatusCode().value());
        assertEquals(2,accounts.count());
        accounts.findAll().forEach(account->{
            assertEquals(AccountRole.USER,account.getRole());
            assertEquals("unchanged-test-hash",account.getPasswordHash());
            assertEquals(0,account.getTokenVersion());
        });
    }
}
