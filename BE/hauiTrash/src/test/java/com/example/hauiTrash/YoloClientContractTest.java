package com.example.hauiTrash;

import com.example.hauiTrash.client.YoloClient;
import org.junit.jupiter.api.Test;
import org.springframework.http.*;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

class YoloClientContractTest {
    @Test void detailedAnalysisDefaultsToTheUsualAiProcess() {
        var client=new YoloClient();ReflectionTestUtils.setField(client,"baseUrl","http://127.0.0.1:8000/");
        var transport=(RestTemplate)ReflectionTestUtils.getField(client,"restTemplate");
        var server=MockRestServiceServer.bindTo(transport).build();
        server.expect(requestTo("http://127.0.0.1:8000/details/predict-image-url"))
            .andExpect(method(HttpMethod.POST)).andExpect(jsonPath("$.request_id").value(7))
            .andRespond(withSuccess("{\"requestId\":7,\"status\":\"COMPLETED\"}",MediaType.APPLICATION_JSON));
        assertEquals(7,client.predictDetailed(7,"https://example.com/a.jpg",java.util.List.of()).getRequestId());
        server.verify();
    }
    @Test void detailedAnalysisUsesSeparateServiceAndSavedParentCoordinates() {
        var client=new YoloClient();ReflectionTestUtils.setField(client,"baseUrl","http://127.0.0.1:8000/");
        ReflectionTestUtils.setField(client,"componentsBaseUrl","http://127.0.0.1:8011/");
        var transport=(RestTemplate)ReflectionTestUtils.getField(client,"restTemplate");
        var server=MockRestServiceServer.bindTo(transport).build();
        server.expect(requestTo("http://127.0.0.1:8011/predict-image-url")).andExpect(method(HttpMethod.POST))
            .andExpect(jsonPath("$.parents[0].id").value(9)).andExpect(jsonPath("$.parents[0].x1").value(10))
            .andExpect(jsonPath("$.conf").doesNotExist()).andRespond(withSuccess("""
              {"requestId":7,"status":"COMPLETED","modelVersion":"experiment-test","experimental":true,
               "imageWidth":100,"imageHeight":200,"componentCount":0,
               "parents":[{"detectionId":9,"componentAnalysisStatus":"COMPLETED","components":[]}]}
              """,MediaType.APPLICATION_JSON));
        var result=client.predictDetailed(7,"https://example.com/a.jpg",java.util.List.of(java.util.Map.of("id",9,"x1",10,"y1",20,"x2",90,"y2",180)));
        assertEquals(7,result.getRequestId());assertEquals("experiment-test",result.getModelVersion());assertTrue(result.getExperimental());server.verify();
    }
    @Test void modelDefaultsArePreservedAndCamelCaseConfirmationIsParsed() {
        var client=new YoloClient();ReflectionTestUtils.setField(client,"baseUrl","http://127.0.0.1:8000/");
        var transport=(RestTemplate)ReflectionTestUtils.getField(client,"restTemplate");
        var server=MockRestServiceServer.bindTo(transport).build();
        server.expect(requestTo("http://127.0.0.1:8000/predict-image-url")).andExpect(method(HttpMethod.POST))
            .andExpect(jsonPath("$.request_id").value(17)).andExpect(jsonPath("$.image_url").value("https://example.com/a.png"))
            .andExpect(jsonPath("$.conf").doesNotExist()).andExpect(jsonPath("$.iou").doesNotExist())
            .andRespond(withSuccess("""
              {"apiVersion":"1","requestId":17,"imageUrl":"https://example.com/a.png","annotatedUrl":"https://example.com/out.png",
               "count":1,"confidenceAvg":0.42,"requiresConfirmation":true,
               "detections":[{"label":"unknown","labelDisplay":"Chưa rõ vật liệu","confidence":0.42,"needsConfirm":true,"x1":1,"y1":2,"x2":3,"y2":4}]}
              """,MediaType.APPLICATION_JSON));
        var result=client.predictByImageUrl(17,"https://example.com/a.png");
        assertEquals(17,result.getRequestId());assertTrue(result.getRequiresConfirmation());
        assertTrue(result.getDetections().getFirst().getNeedsConfirm());assertEquals("unknown",result.getDetections().getFirst().getLabel());
        server.verify();
    }
    @Test void nestedComponentWireContractIsParsedWithoutChangingWholeBottleCount() {
        var client=new YoloClient();ReflectionTestUtils.setField(client,"baseUrl","http://127.0.0.1:8000");
        var transport=(RestTemplate)ReflectionTestUtils.getField(client,"restTemplate");
        var server=MockRestServiceServer.bindTo(transport).build();
        server.expect(requestTo("http://127.0.0.1:8000/predict-image-url"))
            .andRespond(withSuccess("""
              {"apiVersion":"1","componentsApiVersion":1,"count":1,"componentCount":1,
               "analysisMode":"bottle_components","componentModelVersion":"parts-v1",
               "detections":[{"label":"glass","confidence":0.9,"x1":10,"y1":20,"x2":90,"y2":180,
                 "componentAnalysisStatus":"COMPLETED","components":[{"partType":"cap","material":"metal",
                   "detectionConfidence":0.93,"materialConfidence":0.88,"needsConfirm":false,
                   "x1":30,"y1":20,"x2":70,"y2":40}]}]}
              """,MediaType.APPLICATION_JSON));
        var result=client.predictByImageUrl(17,"https://example.com/a.png");
        assertEquals(1,result.getCount());assertEquals(1,result.getComponentsApiVersion());
        assertEquals("parts-v1",result.getComponentModelVersion());
        var component=result.getDetections().getFirst().getComponents().getFirst();
        assertEquals("cap",component.getPartType());assertEquals("metal",component.getMaterial());
        assertEquals(.93f,component.getDetectionConfidence());assertEquals(30,component.getX1());
        server.verify();
    }
}
