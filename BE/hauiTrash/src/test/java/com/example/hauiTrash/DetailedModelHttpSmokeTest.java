package com.example.hauiTrash;

import com.example.hauiTrash.entity.*;
import com.example.hauiTrash.repository.*;
import com.example.hauiTrash.security.JwtUtil;
import com.example.hauiTrash.service.CloudinaryService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import java.nio.file.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/** Opt-in HTTP smoke with a real local AI, using only a disposable H2 database. */
@SpringBootTest(properties={
    "spring.config.import=", "spring.datasource.url=jdbc:h2:mem:detailhttp;MODE=MySQL;DB_CLOSE_DELAY=-1",
    "spring.datasource.username=sa", "spring.datasource.password=", "spring.jpa.database-platform=org.hibernate.dialect.H2Dialect",
    "spring.jpa.hibernate.ddl-auto=create-drop", "spring.sql.init.mode=never", "jwt.secret=local-detail-test-secret-at-least-32-characters",
    "app.admin.bootstrap-enabled=false", "app.admin.email=", "app.admin.phone=", "app.admin.password=",
    "ai.yolo.base-url=http://127.0.0.1:8000", "ai.components.base-url="
})
@AutoConfigureMockMvc
@EnabledIfEnvironmentVariable(named="RUN_DETAIL_HTTP_SMOKE",matches="true")
class DetailedModelHttpSmokeTest {
    @Autowired MockMvc mvc;
    @Autowired AccountRepository accounts;
    @Autowired AiRequestRepository requests;
    @Autowired JwtUtil jwt;
    @Autowired ObjectMapper json;
    @MockitoBean CloudinaryService cloud;

    @Test void savedBottleGoesThroughAuthenticatedBackendAndRealMountedAi() throws Exception {
        var fixture=json.readTree(Files.readString(Path.of(System.getenv("DETAIL_SMOKE_INPUT"))));
        var owner=accounts.save(Account.builder().phone("0901112233").fullName("Disposable H2 smoke test")
            .passwordHash("unused-test-only").role(AccountRole.USER).isActive(true).build());
        var scan=AiRequest.builder().account(owner).cloudinaryUrl(fixture.get("image_url").asText())
            .status(RequestStatus.DONE).analysisMode("bottle").build();
        for(var parent:fixture.get("parents")){
            scan.getDetections().add(Detection.builder().aiRequest(scan).label("glass").labelDisplay("Chai thủy tinh")
                .confidence(.8f).status("CONFIRMED").componentAnalysisStatus("NOT_RUN")
                .x1(parent.get("x1").asInt()).y1(parent.get("y1").asInt())
                .x2(parent.get("x2").asInt()).y2(parent.get("y2").asInt()).build());
        }
        scan=requests.saveAndFlush(scan);
        String route="/api/v1/scans/"+scan.getId(),token="Bearer "+jwt.generateToken(owner.getId(),owner.getRole());
        var before=mvc.perform(get(route).header("Authorization",token)).andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
        var response=mvc.perform(post(route+"/detailed").header("Authorization",token))
            .andExpect(status().isOk()).andExpect(jsonPath("status").value("COMPLETED"))
            .andExpect(jsonPath("experimental").value(true)).andExpect(jsonPath("modelVersion").value("components-experimental-v1"))
            .andReturn().getResponse().getContentAsString();
        var result=json.readTree(response);
        assertTrue(result.get("componentCount").asInt()>0,"Actual photo should yield at least one detected component");
        assertEquals(scan.getDetections().size(),result.get("parents").size());
        var after=mvc.perform(get(route).header("Authorization",token)).andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
        assertEquals(json.readTree(before),json.readTree(after),"Legacy scan/history must stay unchanged");
        verifyNoInteractions(cloud);
        String output=System.getenv("DETAIL_SMOKE_OUTPUT");
        if(output!=null)Files.writeString(Path.of(output),json.writerWithDefaultPrettyPrinter().writeValueAsString(result));
    }
}
