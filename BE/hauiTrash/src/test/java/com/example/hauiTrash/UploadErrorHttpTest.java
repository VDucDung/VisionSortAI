package com.example.hauiTrash;

import com.example.hauiTrash.entity.*;
import com.example.hauiTrash.repository.AccountRepository;
import com.example.hauiTrash.security.JwtUtil;
import com.example.hauiTrash.service.CloudinaryService;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.*;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.util.LinkedMultiValueMap;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

@SpringBootTest(webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT,properties={
    "spring.datasource.url=jdbc:h2:mem:uploaderrors;MODE=MySQL;DB_CLOSE_DELAY=-1",
    "spring.servlet.multipart.max-file-size=1KB", "spring.servlet.multipart.max-request-size=2KB"
})
@ActiveProfiles("test")
class UploadErrorHttpTest {
    // Keep fixture phones at ten digits; nanoTime modulo can yield short numbers.
    private static final java.util.concurrent.atomic.AtomicInteger PHONE_SEQUENCE =
        new java.util.concurrent.atomic.AtomicInteger(1_000_000);
    @Autowired TestRestTemplate http;
    @Autowired AccountRepository accounts;
    @Autowired JwtUtil jwt;
    @MockitoBean CloudinaryService images;
    HttpHeaders headers;
    @BeforeEach void setup() {
        var a=accounts.save(Account.builder().phone("090"+PHONE_SEQUENCE.incrementAndGet())
            .fullName("HTTP regression").passwordHash("test-only").role(AccountRole.USER).isActive(true).build());
        headers=new HttpHeaders();headers.setBearerAuth(jwt.generateToken(a.getId(),a.getRole()));
    }
    ResponseEntity<String> upload(int length) {
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        var parts=new LinkedMultiValueMap<String,Object>();
        parts.add("file",new ByteArrayResource(new byte[length]) { @Override public String getFilename(){return "test.png";} });
        return http.exchange("/api/v1/scans",HttpMethod.POST,new HttpEntity<>(parts,headers),String.class);
    }
    @Test void internalUploadErrorMustNotBecomeAnAuthenticationError() {
        when(images.uploadImage(any())).thenThrow(new IllegalStateException("simulated internal failure"));
        var result=upload(10);assertEquals(500,result.getStatusCode().value());
    }
    @Test void oversizedMultipartMustKeep413() { assertEquals(413,upload(4096).getStatusCode().value()); }
    @Test void unknownScanRouteMustKeep404() {
        var result=http.exchange("/api/v1/scans/not/a/route",HttpMethod.GET,new HttpEntity<>(headers),String.class);
        assertEquals(404,result.getStatusCode().value());
    }
    @Test void runtimeCapabilityIsPublicAndIdentifiesCurrentScanApi() {
        var result=http.getForEntity("/api/v1/system/info",String.class);
        assertEquals(200,result.getStatusCode().value());
        assertTrue(result.getBody().contains("\"scanApiVersion\":1"));
        assertTrue(result.getBody().contains("20261107-hitl"));
        assertTrue(result.getBody().contains("\"adminProfileApiVersion\":1"));
        assertTrue(result.getBody().contains("\"componentsApiVersion\":1"));
        assertTrue(result.getBody().contains("\"detailedAnalysisApiVersion\":1"));
        assertTrue(result.getBody().contains("\"hitlApiVersion\":1"));
    }
}
