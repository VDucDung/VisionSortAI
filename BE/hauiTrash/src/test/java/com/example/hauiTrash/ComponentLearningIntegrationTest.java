package com.example.hauiTrash;

import com.example.hauiTrash.client.YoloClient;
import com.example.hauiTrash.dto.*;
import com.example.hauiTrash.entity.*;
import com.example.hauiTrash.repository.*;
import com.example.hauiTrash.security.JwtUtil;
import com.example.hauiTrash.service.CloudinaryService;
import com.fasterxml.jackson.databind.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.http.MediaType;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties={"spring.config.import=","spring.datasource.url=jdbc:h2:mem:hitl;MODE=MySQL;DB_CLOSE_DELAY=-1",
    "spring.datasource.username=sa","spring.datasource.password=","spring.jpa.database-platform=org.hibernate.dialect.H2Dialect",
    "spring.jpa.hibernate.ddl-auto=create-drop","spring.sql.init.mode=never","jwt.secret=hitl-test-only-secret-with-at-least-32-characters",
    "app.admin.bootstrap-enabled=false","app.admin.email=","app.admin.password=","app.admin.phone="})
@AutoConfigureMockMvc
class ComponentLearningIntegrationTest {
    @Autowired MockMvc mvc;@Autowired ObjectMapper json;@Autowired JwtUtil jwt;
    @Autowired AccountRepository accounts;@Autowired AiRequestRepository scans;@Autowired ComponentLearningCaseRepository cases;
    @MockitoBean YoloClient model;@MockitoBean CloudinaryService cloud;
    static AtomicInteger sequence=new AtomicInteger(3000000);
    Account owner,other,admin;AiRequest scan;String labelCase;long beforeCases;
    Account account(AccountRole role){return accounts.save(Account.builder().phone("091"+sequence.incrementAndGet()).fullName("HITL test")
        .passwordHash("not-used-in-test").role(role).isActive(true).build());}
    String token(Account a){return "Bearer "+jwt.generateToken(a.getId(),a.getRole());}
    String route(){return "/api/v1/scans/"+scan.getId();}
    @BeforeEach void setup() throws Exception {
        owner=account(AccountRole.USER);other=account(AccountRole.USER);admin=account(AccountRole.ADMIN);beforeCases=cases.count();
        scan=AiRequest.builder().account(owner).status(RequestStatus.DONE).cloudinaryUrl("https://example.com/bottle.jpg").analysisMode("bottle").build();
        var parent=Detection.builder().aiRequest(scan).label("glass").labelDisplay("Chai thủy tinh").confidence(.9f)
            .status("DETECTED").componentAnalysisStatus("NOT_RUN").x1(0).y1(0).x2(100).y2(200).build();scan.getDetections().add(parent);scan=scans.saveAndFlush(scan);
        var response=new DetailedAnalysisDTO();response.setRequestId(scan.getId());response.setStatus("COMPLETED");response.setExperimental(true);
        response.setModelVersion("test-hitl-v1");response.setImageWidth(100);response.setImageHeight(200);response.setComponentCount(3);
        var p=new DetailedAnalysisDTO.ParentDTO();p.setDetectionId(parent.getId());p.setComponentAnalysisStatus("COMPLETED");
        p.setComponents(List.of(component("body","plastic",.96f,20,40,90,190),component("cap","plastic",.91f,40,0,70,30),component("label","paper",.54f,25,70,85,120)));
        response.setParents(List.of(p));when(model.predictDetailed(eq(scan.getId()),anyString(),anyList())).thenReturn(response);
        var detail=analyze();labelCase=detail.get("parents").get(0).get("components").get(2).get("learningCaseId").asText();
    }
    AiResponseDetailsDTO.ComponentDTO component(String part,String material,float score,int x1,int y1,int x2,int y2){return AiResponseDetailsDTO.ComponentDTO.builder()
        .partType(part).material(material).materialConfidence(score).detectionConfidence(.9f).x1(x1).y1(y1).x2(x2).y2(y2).build();}
    JsonNode analyze() throws Exception{return json.readTree(mvc.perform(post(route()+"/detailed").header("Authorization",token(owner)))
        .andExpect(status().isOk()).andReturn().getResponse().getContentAsString());}
    Map<String,Object> answer(String material,String basis,boolean region,boolean consent){return new HashMap<>(Map.of("material",material,"verificationBasis",basis,"regionCorrect",region,"trainingConsent",consent,"revision",0,"note","Đã kiểm tra"));}
    JsonNode feedback(Map<String,Object> body) throws Exception{return json.readTree(mvc.perform(post(route()+"/learning/"+labelCase+"/feedback").header("Authorization",token(owner))
        .contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(body))).andExpect(status().isOk()).andReturn().getResponse().getContentAsString());}
    JsonNode export() throws Exception{return json.readTree(mvc.perform(get("/api/v1/admin/learning/export").header("Authorization",token(admin)))
        .andExpect(status().isOk()).andReturn().getResponse().getContentAsString());}
    @Test void repeatAnalysisDeduplicatesSnapshotsAndPrioritizesTheUncertainLabel() throws Exception {
        var response=analyze();assertEquals(beforeCases+3,cases.count());
        var components=response.get("parents").get(0).get("components");assertFalse(components.get(0).get("queryRecommended").asBoolean());
        assertTrue(components.get(2).get("queryRecommended").asBoolean());assertEquals(labelCase,components.get(2).get("learningCaseId").asText());
        mvc.perform(get(route()).header("Authorization",token(owner))).andExpect(status().isOk()).andExpect(jsonPath("componentCount").value(0))
            .andExpect(jsonPath("detections[0].label").value("glass"));verifyNoInteractions(cloud);
    }
    @Test void onlyOwnerCanSubmitAndOnlyAdminCanReviewOrExport() throws Exception {
        var body=json.writeValueAsString(answer("plastic","PHYSICAL_CHECK",true,true));
        for(var actor:List.of(other,admin))mvc.perform(post(route()+"/learning/"+labelCase+"/feedback").header("Authorization",token(actor)).contentType(MediaType.APPLICATION_JSON).content(body)).andExpect(status().isForbidden());
        mvc.perform(post(route()+"/learning/"+labelCase+"/feedback").contentType(MediaType.APPLICATION_JSON).content(body)).andExpect(status().isUnauthorized());
        mvc.perform(get(route()+"/learning").header("Authorization",token(other))).andExpect(status().isForbidden());
        mvc.perform(get("/api/v1/admin/learning").header("Authorization",token(owner))).andExpect(status().isForbidden());
        mvc.perform(get("/api/v1/admin/learning/export").header("Authorization",token(owner))).andExpect(status().isForbidden());
    }
    @Test void humanCorrectionOnlyEntersTrainingAfterIndependentReviewAndNeverChangesAiPrediction() throws Exception {
        long exportedBefore=export().get("records").size();
        var pending=feedback(answer("plastic","PHYSICAL_CHECK",true,true));assertEquals("PENDING",pending.get("feedbackState").asText());
        assertEquals(exportedBefore,export().get("records").size());
        mvc.perform(post("/api/v1/admin/learning/"+labelCase+"/review").header("Authorization",token(admin)).contentType(MediaType.APPLICATION_JSON)
            .content(json.writeValueAsString(Map.of("decision","APPROVE","revision",pending.get("revision").asLong(),"note","Đủ căn cứ")))).andExpect(status().isOk());
        var row=export().get("records");assertEquals(exportedBefore+1,row.size());
        boolean found=false;for(var item:row)if(item.get("caseId").asText().equals(labelCase)){found=true;assertEquals("plastic",item.get("material").asText());assertTrue(item.get("adminReviewed").asBoolean());assertFalse(item.has("accountId"));}
        assertTrue(found);var saved=analyze().get("parents").get(0).get("components").get(2);
        assertEquals("paper",saved.get("material").asText());assertEquals("plastic",saved.get("humanMaterial").asText());assertEquals("APPROVED",saved.get("feedbackState").asText());
    }
    @Test void unknownVisualOnlyMissingConsentAndWrongRegionsCannotBeApprovedForTraining() throws Exception {
        for(int i=0;i<4;i++){
            String id=labelCase;
            if(i>0){var component=analyze().get("parents").get(0).get("components").get(i==3?0:1);id=component.get("learningCaseId").asText();}
            // A previous cap submission intentionally cannot be overwritten.
            if(i==2){mvc.perform(post(route()+"/learning/"+id+"/feedback").header("Authorization",token(owner)).contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(answer("plastic","PHYSICAL_CHECK",true,false)))).andExpect(status().isConflict());continue;}
            var body=i==0?answer("unknown","UNSURE",true,true):i==1?answer("plastic","VISUAL_ONLY",true,true):answer("plastic","PHYSICAL_CHECK",false,false);
            var submitted=mvc.perform(post(route()+"/learning/"+id+"/feedback").header("Authorization",token(owner)).contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(body)))
                .andExpect(status().isOk()).andReturn();
            long revision=json.readTree(submitted.getResponse().getContentAsString()).get("revision").asLong();
            mvc.perform(post("/api/v1/admin/learning/"+id+"/review").header("Authorization",token(admin)).contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("decision","APPROVE","revision",revision)))).andExpect(status().isBadRequest());
        }
    }
    @Test void forgedMaterialsOversizedNotesAndStaleDecisionsAreRejected() throws Exception {
        var invalid=answer("wood","PHYSICAL_CHECK",true,true);
        mvc.perform(post(route()+"/learning/"+labelCase+"/feedback").header("Authorization",token(owner)).contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(invalid))).andExpect(status().isBadRequest());
        invalid=answer("plastic","PHYSICAL_CHECK",true,true);invalid.put("note","x".repeat(1001));
        mvc.perform(post(route()+"/learning/"+labelCase+"/feedback").header("Authorization",token(owner)).contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(invalid))).andExpect(status().isBadRequest());
        feedback(answer("plastic","PHYSICAL_CHECK",true,true));
        mvc.perform(post("/api/v1/admin/learning/"+labelCase+"/review").header("Authorization",token(admin)).contentType(MediaType.APPLICATION_JSON)
            .content("{\"decision\":\"APPROVE\",\"revision\":0}")).andExpect(status().isConflict());
    }
    @Test void aCorrectKnownRegionWithoutConsentStillCannotBeApproved() throws Exception {
        var pending=feedback(answer("plastic","PHYSICAL_CHECK",true,false));
        mvc.perform(post("/api/v1/admin/learning/"+labelCase+"/review").header("Authorization",token(admin)).contentType(MediaType.APPLICATION_JSON)
            .content(json.writeValueAsString(Map.of("decision","APPROVE","revision",pending.get("revision").asLong())))).andExpect(status().isBadRequest());
    }
    @org.junit.jupiter.params.ParameterizedTest
    @org.junit.jupiter.params.provider.ValueSource(strings={"VISUAL_REVIEW","PHYSICAL_CHECK","PACKAGING_MARK"})
    void adminCanVerifyIndependentlyWithoutChangingTheUsersOriginalBasis(String basis) throws Exception {
        var pending=feedback(answer("plastic","VISUAL_ONLY",true,true));
        mvc.perform(post("/api/v1/admin/learning/"+labelCase+"/review").header("Authorization",token(admin)).contentType(MediaType.APPLICATION_JSON)
            .content(json.writeValueAsString(Map.of("decision","APPROVE","revision",pending.get("revision").asLong(),
                "verificationBasis",basis,"confirmedCorrect",true,"note","Admin đã kiểm chứng nhãn là nhựa"))))
            .andExpect(status().isOk()).andExpect(jsonPath("feedbackState").value("APPROVED"))
            .andExpect(jsonPath("verificationBasis").value("VISUAL_ONLY"))
            .andExpect(jsonPath("adminVerificationBasis").value(basis));
        boolean found=false;
        for(var row:export().get("records"))if(row.get("caseId").asText().equals(labelCase)){
            found=true;assertEquals("VISUAL_ONLY",row.get("userVerificationBasis").asText());
            assertEquals(basis,row.get("adminVerificationBasis").asText());assertEquals("ADMIN",row.get("verificationSource").asText());
            assertEquals("VISUAL_REVIEW".equals(basis)?"ADMIN_VISUAL_REVIEW":basis,row.get("verificationBasis").asText());
        }
        assertTrue(found);
    }
    @Test void independentVerificationRequiresExplicitConfirmationAndNote() throws Exception {
        var pending=feedback(answer("plastic","VISUAL_ONLY",true,true));
        for(boolean missingNote:List.of(true,false)){
            var body=Map.of("decision","APPROVE","revision",pending.get("revision").asLong(),"verificationBasis","VISUAL_REVIEW",
                "confirmedCorrect",missingNote,"note",missingNote?"":"Chỉ ghi chú chưa tích xác nhận");
            mvc.perform(post("/api/v1/admin/learning/"+labelCase+"/review").header("Authorization",token(admin)).contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(body))).andExpect(status().isBadRequest());
        }
        assertNull(cases.findById(labelCase).orElseThrow().getAdminVerificationBasis());
    }
    @org.junit.jupiter.params.ParameterizedTest
    @org.junit.jupiter.params.provider.ValueSource(booleans={true,false})
    void adminVerificationDoesNotOverrideMissingConsentOrWrongRegion(boolean regionCorrect) throws Exception {
        var pending=feedback(answer("plastic","VISUAL_ONLY",regionCorrect,!regionCorrect));
        mvc.perform(post("/api/v1/admin/learning/"+labelCase+"/review").header("Authorization",token(admin)).contentType(MediaType.APPLICATION_JSON)
            .content(json.writeValueAsString(Map.of("decision","APPROVE","revision",pending.get("revision").asLong(),
                "verificationBasis","PHYSICAL_CHECK","confirmedCorrect",true,"note","Admin đã kiểm tra trực tiếp"))))
            .andExpect(status().isBadRequest());
        assertNull(cases.findById(labelCase).orElseThrow().getAdminVerificationBasis());
    }
    @Test void rejectionNeedsReasonAndDuplicateSubmissionsDoNotRewriteAudit() throws Exception {
        var body=answer("plastic","PHYSICAL_CHECK",true,true);var pending=feedback(body);
        mvc.perform(post(route()+"/learning/"+labelCase+"/feedback").header("Authorization",token(owner)).contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(body))).andExpect(status().isConflict());
        var decision=new HashMap<String,Object>(Map.of("decision","REJECT","revision",pending.get("revision").asLong()));
        mvc.perform(post("/api/v1/admin/learning/"+labelCase+"/review").header("Authorization",token(admin)).contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(decision))).andExpect(status().isBadRequest());
        decision.put("note","Vùng nhãn chưa đúng");
        mvc.perform(post("/api/v1/admin/learning/"+labelCase+"/review").header("Authorization",token(admin)).contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(decision)))
            .andExpect(status().isOk()).andExpect(jsonPath("feedbackState").value("REJECTED"));
    }
}
