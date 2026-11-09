package com.example.hauiTrash;

import com.example.hauiTrash.client.YoloClient;
import com.example.hauiTrash.dto.YoloPredictResponseDTO;
import com.example.hauiTrash.entity.*;
import com.example.hauiTrash.repository.*;
import com.example.hauiTrash.security.JwtUtil;
import com.example.hauiTrash.service.CloudinaryService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.http.MediaType;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(properties = {
    "spring.config.import=", "spring.datasource.url=jdbc:h2:mem:workspace;MODE=MySQL;DB_CLOSE_DELAY=-1", "spring.datasource.username=sa", "spring.datasource.password=",
    "spring.jpa.database-platform=org.hibernate.dialect.H2Dialect", "spring.jpa.hibernate.ddl-auto=create-drop", "spring.sql.init.mode=never",
    "jwt.secret=test-only-secret-with-at-least-32-characters", "app.admin.email=", "app.admin.password=", "app.admin.phone="
})
@AutoConfigureMockMvc
class ScanWorkspaceIntegrationTest {
    @Autowired MockMvc mvc;
    @Autowired AccountRepository accounts;
    @Autowired AiRequestRepository requests;
    @Autowired JwtUtil jwt;
    @Autowired ObjectMapper json;
    @Autowired org.springframework.security.crypto.password.PasswordEncoder passwords;
    @Autowired com.example.hauiTrash.config.AdminBootstrap bootstrap;
    @MockitoBean CloudinaryService cloud;
    @MockitoBean YoloClient model;
    static AtomicInteger sequence = new AtomicInteger(1000000);
    Account owner, other, admin;
    @BeforeEach void setup() {
        owner = account(AccountRole.USER); other = account(AccountRole.USER); admin = account(AccountRole.ADMIN);
        when(cloud.uploadImage(any())).thenReturn("https://res.cloudinary.com/example/original.png");
        var detection = new YoloPredictResponseDTO.DetectionDTO(); detection.setLabel("plastic"); detection.setLabelDisplay("Chai nhựa");
        detection.setConfidence(.93f); detection.setNeedsConfirm(true); detection.setX1(3); detection.setY1(4); detection.setX2(20); detection.setY2(30);
        var result = new YoloPredictResponseDTO(); result.setDetections(List.of(detection)); result.setAnnotatedUrl("https://res.cloudinary.com/example/annotated.png");
        when(model.predictByImageUrl(anyInt(), anyString())).thenReturn(result);
    }
    Account account(AccountRole role) {
        int n = sequence.incrementAndGet();
        return accounts.save(Account.builder().phone("090" + n).email(n + "@example.com").fullName("Người dùng " + n)
            .passwordHash(passwords.encode("Testpassword2026!")).role(role).isActive(true).build());
    }
    String token(Account a) { return "Bearer " + jwt.generateToken(a.getId(), a.getRole()); }
    int scan() throws Exception {
        var response = mvc.perform(multipart("/api/v1/scans").file(new MockMultipartFile("file","test.png","image/png",new byte[]{1,2}))
            .header("Authorization",token(owner))).andExpect(status().isOk()).andExpect(jsonPath("status").value("DONE"))
            .andExpect(jsonPath("requiresConfirmation").value(true)).andExpect(jsonPath("detections[0].status").value("NEEDS_CONFIRM"))
            .andExpect(jsonPath("detections[0].label").value("plastic")).andReturn();
        return json.readTree(response.getResponse().getContentAsString()).get("id").asInt();
    }
    @Test void detailedEndpointUsesSavedParentsAndPreservesLegacyHistory() throws Exception {
        int id=scan();
        var before=mvc.perform(get("/api/v1/scans/"+id).header("Authorization",token(owner)))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
        int detectionId=json.readTree(before).get("detections").get(0).get("id").asInt();
        var detail=new com.example.hauiTrash.dto.DetailedAnalysisDTO();
        detail.setRequestId(id);detail.setStatus("COMPLETED");detail.setExperimental(true);detail.setModelVersion("experiment-test");
        detail.setImageWidth(100);detail.setImageHeight(100);detail.setComponentCount(1);
        var parent=new com.example.hauiTrash.dto.DetailedAnalysisDTO.ParentDTO();parent.setDetectionId(detectionId);
        parent.setComponentAnalysisStatus("COMPLETED");
        parent.setComponents(List.of(com.example.hauiTrash.dto.AiResponseDetailsDTO.ComponentDTO.builder()
            .partType("cap").material("unknown").detectionConfidence(.8f).materialConfidence(.5f)
            .x1(4).y1(5).x2(10).y2(12).build()));detail.setParents(List.of(parent));
        when(model.predictDetailed(eq(id),anyString(),anyList())).thenReturn(detail);
        mvc.perform(post("/api/v1/scans/"+id+"/detailed")).andExpect(status().isUnauthorized());
        mvc.perform(post("/api/v1/scans/"+id+"/detailed").header("Authorization",token(other))).andExpect(status().isForbidden());
        verify(model,never()).predictDetailed(anyInt(),anyString(),anyList());
        mvc.perform(post("/api/v1/scans/"+id+"/detailed").header("Authorization",token(owner)))
            .andExpect(status().isOk()).andExpect(jsonPath("componentCount").value(1))
            .andExpect(jsonPath("parents[0].components[0].material").value("unknown"))
            .andExpect(jsonPath("parents[0].components[0].status").value("NEEDS_CONFIRM"));
        verify(model).predictDetailed(eq(id),eq("https://res.cloudinary.com/example/original.png"),
            eq(List.of(java.util.Map.of("id",detectionId,"x1",3,"y1",4,"x2",20,"y2",30))));
        mvc.perform(post("/api/v1/scans/"+id+"/detailed").header("Authorization",token(admin))).andExpect(status().isOk());
        var after=mvc.perform(get("/api/v1/scans/"+id).header("Authorization",token(owner)))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
        assertEquals(json.readTree(before),json.readTree(after));
        verify(model,times(1)).predictByImageUrl(anyInt(),anyString());
    }
    @Test void failedDetailedServiceDoesNotChangeSavedScanOrSession() throws Exception {
        int id=scan();
        when(model.predictDetailed(eq(id),anyString(),anyList())).thenThrow(new RuntimeException("offline"));
        mvc.perform(post("/api/v1/scans/"+id+"/detailed").header("Authorization",token(owner)))
            .andExpect(status().isServiceUnavailable());
        mvc.perform(get("/api/v1/scans/"+id).header("Authorization",token(owner)))
            .andExpect(status().isOk()).andExpect(jsonPath("status").value("DONE"))
            .andExpect(jsonPath("count").value(1)).andExpect(jsonPath("componentCount").value(0));
        verify(model,times(1)).predictByImageUrl(anyInt(),anyString());
    }
    @Test void authenticationRolesAndRetiredRoutes() throws Exception {
        mvc.perform(get("/api/v1/scans")).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/v1/admin/statistics").header("Authorization",token(owner))).andExpect(status().isForbidden());
        mvc.perform(get("/api/v1/admin/quizzes").header("Authorization",token(admin))).andExpect(status().isForbidden());
        mvc.perform(post("/api/v1/auth/register").contentType(MediaType.APPLICATION_JSON)
            .content("{\"phone\":\"0912345678\",\"password\":\"short\",\"fullName\":\"Test\",\"role\":\"ADMIN\"}" )).andExpect(status().isBadRequest());
    }
    @Test void realLoginRegistrationAndCorsContract() throws Exception {
        String phone="090"+sequence.incrementAndGet();
        mvc.perform(post("/api/v1/auth/register").contentType(MediaType.APPLICATION_JSON)
            .content("{\"phone\":\""+phone+"\",\"password\":\"Testpassword2026!\",\"fullName\":\"New User\",\"role\":\"ADMIN\"}"))
            .andExpect(status().isOk()).andExpect(jsonPath("data.account.role").value("USER")).andExpect(jsonPath("data.token").isString());
        mvc.perform(post("/api/v1/auth/login/user").contentType(MediaType.APPLICATION_JSON)
            .content("{\"identifier\":\""+phone+"\",\"password\":\"Testpassword2026!\"}"))
            .andExpect(status().isOk()).andExpect(jsonPath("data.account.role").value("USER"));
        mvc.perform(post("/api/v1/auth/login/admin").contentType(MediaType.APPLICATION_JSON)
            .content("{\"identifier\":\""+admin.getEmail()+"\",\"password\":\"Testpassword2026!\"}"))
            .andExpect(status().isOk()).andExpect(jsonPath("data.account.role").value("ADMIN"));
        mvc.perform(post("/api/v1/auth/login/admin").contentType(MediaType.APPLICATION_JSON)
            .content("{\"identifier\":\""+owner.getEmail()+"\",\"password\":\"Testpassword2026!\"}"))
            .andExpect(status().isForbidden());
        mvc.perform(options("/api/v1/scans").header("Origin","http://127.0.0.1:5173").header("Access-Control-Request-Method","POST"))
            .andExpect(status().isOk()).andExpect(header().string("Access-Control-Allow-Origin","http://127.0.0.1:5173"));
        mvc.perform(options("/api/v1/scans").header("Origin","https://untrusted.example").header("Access-Control-Request-Method","POST"))
            .andExpect(status().isForbidden());
    }
    @Test void explicitAdminProvisioningChangesOnlyTheSelectedAccountAndNewPasswordWorks() throws Exception {
        String[] fields={"email","phone","password","updateExisting","enabled"};
        Object[] previous=java.util.Arrays.stream(fields).map(name->org.springframework.test.util.ReflectionTestUtils.getField(bootstrap,name)).toArray();
        long before=accounts.count();
        try {
            org.springframework.test.util.ReflectionTestUtils.setField(bootstrap,"email",owner.getEmail());
            org.springframework.test.util.ReflectionTestUtils.setField(bootstrap,"phone","");
            org.springframework.test.util.ReflectionTestUtils.setField(bootstrap,"password","New-admin-pass-2026!");
            org.springframework.test.util.ReflectionTestUtils.setField(bootstrap,"updateExisting",true);
            org.springframework.test.util.ReflectionTestUtils.setField(bootstrap,"enabled",true);
            bootstrap.run(null);
            var updated=accounts.findById(owner.getId()).orElseThrow();
            assertEquals(AccountRole.ADMIN,updated.getRole());assertEquals(owner.getPhone(),updated.getPhone());
            assertEquals(owner.getFullName(),updated.getFullName());assertEquals(before,accounts.count());
            assertEquals(AccountRole.USER,accounts.findById(other.getId()).orElseThrow().getRole());
            mvc.perform(post("/api/v1/auth/login/admin").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(java.util.Map.of("identifier"," "+owner.getEmail().toUpperCase(java.util.Locale.ROOT)+" ","password","New-admin-pass-2026!"))))
                .andExpect(status().isOk()).andExpect(jsonPath("data.account.id").value(owner.getId())).andExpect(jsonPath("data.account.role").value("ADMIN"));
            mvc.perform(post("/api/v1/auth/login/admin").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(java.util.Map.of("identifier",owner.getEmail(),"password","Testpassword2026!"))))
                .andExpect(status().isUnauthorized());
        } finally {
            for(int i=0;i<fields.length;i++)org.springframework.test.util.ReflectionTestUtils.setField(bootstrap,fields[i],previous[i]);
        }
    }
    @Test void activeProcessingIsNotDuplicatedAndAbandonedWorkCanRecover() throws Exception {
        var request=requests.save(AiRequest.builder().account(owner).cloudinaryUrl("https://example.com/image.png")
            .status(RequestStatus.PROCESSING).processingAt(java.time.Instant.now()).build());
        mvc.perform(post("/api/v1/scans/"+request.getId()+"/retry").header("Authorization",token(owner))).andExpect(status().isConflict());
        verifyNoInteractions(model);
        request.setProcessingAt(java.time.Instant.now().minusSeconds(360));requests.save(request);
        mvc.perform(post("/api/v1/scans/"+request.getId()+"/retry").header("Authorization",token(owner))).andExpect(status().isOk());
        verify(model,times(1)).predictByImageUrl(anyInt(),anyString());
    }
    @Test void ownerIsolationFiltersAndIdempotency() throws Exception {
        int id=scan();
        mvc.perform(get("/api/v1/scans/"+id).header("Authorization",token(other))).andExpect(status().isForbidden());
        mvc.perform(post("/api/v1/scans/"+id+"/retry").header("Authorization",token(other))).andExpect(status().isForbidden());
        mvc.perform(get("/api/v1/scans?q="+id).header("Authorization",token(other))).andExpect(status().isOk()).andExpect(jsonPath("total").value(0));
        mvc.perform(get("/api/v1/scans?material=plastic&q="+id).header("Authorization",token(owner))).andExpect(status().isOk()).andExpect(jsonPath("items[0].id").value(id));
        mvc.perform(post("/api/v1/scans/"+id+"/retry").header("Authorization",token(owner))).andExpect(status().isOk());
        verify(model,times(1)).predictByImageUrl(anyInt(),anyString());
        mvc.perform(get("/api/v1/scans/"+id).header("Authorization",token(admin))).andExpect(status().isOk()).andExpect(jsonPath("count").value(1));
    }
    @Test void failureIsPersistedAndCanBeRetried() throws Exception {
        when(model.predictByImageUrl(anyInt(),anyString())).thenThrow(new RuntimeException("offline"));
        mvc.perform(multipart("/api/v1/scans").file(new MockMultipartFile("file","t.png","image/png",new byte[]{1}))
            .header("Authorization",token(owner))).andExpect(status().isBadGateway());
        var failed=requests.findHistoryByAccountId(owner.getId()).getFirst(); assertEquals(RequestStatus.ERROR,failed.getStatus());
        reset(model);var result=new YoloPredictResponseDTO();result.setDetections(List.of());result.setAnnotatedUrl("https://example.com/no-detections.png");
        when(model.predictByImageUrl(anyInt(),anyString())).thenReturn(result);
        mvc.perform(post("/api/v1/scans/"+failed.getId()+"/retry").header("Authorization",token(owner)))
            .andExpect(status().isOk()).andExpect(jsonPath("count").value(0)).andExpect(jsonPath("annotatedUrl").value(result.getAnnotatedUrl()));
    }
    @Test void adminStatisticsAndLockedSession() throws Exception {
        scan();
        mvc.perform(get("/api/v1/admin/statistics").header("Authorization",token(admin))).andExpect(status().isOk())
            .andExpect(jsonPath("daily").isArray()).andExpect(jsonPath("needsConfirmation").isNumber()).andExpect(jsonPath("materials").isArray());
        mvc.perform(get("/api/v1/admin/users?q="+owner.getPhone()).header("Authorization",token(admin))).andExpect(status().isOk())
            .andExpect(jsonPath("items[0].id").value(owner.getId())).andExpect(jsonPath("items[0].passwordHash").doesNotExist());
        mvc.perform(patch("/api/v1/admin/users/"+owner.getId()).header("Authorization",token(admin)).contentType(MediaType.APPLICATION_JSON)
            .content(json.writeValueAsString(new com.example.hauiTrash.controller.AdminWorkspaceController.UserUpdate("Đã khóa",owner.getPhone(),owner.getEmail(),false))))
            .andExpect(status().isOk()).andExpect(jsonPath("active").value(false));
        mvc.perform(get("/api/v1/scans").header("Authorization",token(owner))).andExpect(status().isUnauthorized());
        mvc.perform(patch("/api/v1/admin/users/"+admin.getId()).header("Authorization",token(admin)).contentType(MediaType.APPLICATION_JSON)
            .content(json.writeValueAsString(new com.example.hauiTrash.controller.AdminWorkspaceController.UserUpdate("Admin",admin.getPhone(),admin.getEmail(),false))))
            .andExpect(status().isNotFound());
    }

    private YoloPredictResponseDTO componentResponse() {
        var result = new YoloPredictResponseDTO();
        result.setComponentsApiVersion(1); result.setComponentModelVersion("test-parts-v1");
        var bottle = new YoloPredictResponseDTO.DetectionDTO();
        bottle.setLabel("plastic"); bottle.setConfidence(.93f); bottle.setX1(3); bottle.setY1(4); bottle.setX2(20); bottle.setY2(30);
        bottle.setComponentAnalysisStatus("COMPLETED");
        var cap = new YoloPredictResponseDTO.ComponentDTO();
        cap.setPartType("cap"); cap.setMaterial("metal"); cap.setDetectionConfidence(.9f); cap.setMaterialConfidence(.8f);
        cap.setX1(3); cap.setY1(4); cap.setX2(20); cap.setY2(8);
        var body = new YoloPredictResponseDTO.ComponentDTO();
        body.setPartType("body"); body.setMaterial("glass"); body.setDetectionConfidence(.95f); body.setMaterialConfidence(.92f);
        body.setX1(3); body.setY1(8); body.setX2(20); body.setY2(30);
        var label = new YoloPredictResponseDTO.ComponentDTO();
        label.setPartType("label"); label.setMaterial("unknown"); label.setDetectionConfidence(.9f); label.setMaterialConfidence(.34f); label.setNeedsConfirm(true);
        label.setX1(4); label.setY1(14); label.setX2(18); label.setY2(22);
        bottle.setComponents(List.of(cap,body,label)); result.setDetections(List.of(bottle));
        return result;
    }

    @Test void componentsPersistWithParentOwnershipAndSeparateCounts() throws Exception {
        when(model.predictByImageUrl(anyInt(),anyString())).thenReturn(componentResponse());
        var response = mvc.perform(multipart("/api/v1/scans").file(new MockMultipartFile("file","test.png","image/png",new byte[]{1}))
            .header("Authorization",token(owner))).andExpect(status().isOk())
            .andExpect(jsonPath("count").value(1)).andExpect(jsonPath("componentCount").value(3))
            .andExpect(jsonPath("analysisMode").value("bottle_components"))
            .andExpect(jsonPath("componentModelVersion").value("test-parts-v1"))
            .andExpect(jsonPath("detections[0].components[1].material").value("glass"))
            .andExpect(jsonPath("detections[0].components[2].status").value("NEEDS_CONFIRM"))
            .andExpect(jsonPath("requiresConfirmation").value(true)).andReturn();
        int id = json.readTree(response.getResponse().getContentAsString()).get("id").asInt();
        mvc.perform(get("/api/v1/scans/"+id).header("Authorization",token(other))).andExpect(status().isForbidden());
        mvc.perform(get("/api/v1/scans?q="+id+"&material=glass").header("Authorization",token(owner)))
            .andExpect(status().isOk()).andExpect(jsonPath("items[0].componentCount").value(3));
        mvc.perform(post("/api/v1/scans/"+id+"/retry").header("Authorization",token(owner)))
            .andExpect(status().isOk()).andExpect(jsonPath("componentCount").value(3));
        verify(model,times(1)).predictByImageUrl(anyInt(),anyString());
        mvc.perform(get("/api/v1/admin/statistics").header("Authorization",token(admin)))
            .andExpect(status().isOk()).andExpect(jsonPath("totalComponents").isNumber())
            .andExpect(jsonPath("componentMaterials").isArray());
    }

    @Test void invalidComponentBoxesAreNotStoredAsSuccessfulScans() throws Exception {
        var invalid = componentResponse(); invalid.getDetections().getFirst().getComponents().getFirst().setX2(900);
        when(model.predictByImageUrl(anyInt(),anyString())).thenReturn(invalid);
        mvc.perform(multipart("/api/v1/scans").file(new MockMultipartFile("file","test.png","image/png",new byte[]{1}))
            .header("Authorization",token(owner))).andExpect(status().isBadGateway());
        var failed = requests.findHistoryByAccountId(owner.getId()).getFirst();
        assertEquals(RequestStatus.ERROR, failed.getStatus());
        mvc.perform(get("/api/v1/scans/"+failed.getId()).header("Authorization",token(owner)))
            .andExpect(status().isOk()).andExpect(jsonPath("componentCount").value(0));
    }

    @Test void legacyAiResultsRemainUsableWithoutInventingComponents() throws Exception {
        int id = scan();
        mvc.perform(get("/api/v1/scans/"+id).header("Authorization",token(owner)))
            .andExpect(status().isOk()).andExpect(jsonPath("componentCount").value(0))
            .andExpect(jsonPath("analysisMode").value("bottle"))
            .andExpect(jsonPath("detections[0].componentAnalysisStatus").value("NOT_RUN"))
            .andExpect(jsonPath("detections[0].components").isEmpty());
    }
}
