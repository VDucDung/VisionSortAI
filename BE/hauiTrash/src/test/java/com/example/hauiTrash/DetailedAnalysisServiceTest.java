package com.example.hauiTrash;

import com.example.hauiTrash.client.YoloClient;
import com.example.hauiTrash.dto.*;
import com.example.hauiTrash.entity.RequestStatus;
import com.example.hauiTrash.service.*;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class DetailedAnalysisServiceTest {
    AiResponseDetailsDTO scan() {
        return AiResponseDetailsDTO.builder().id(7).status(RequestStatus.DONE).cloudinaryUrl("https://example.com/a.jpg")
            .count(1).confidenceAvg(.94f).detections(List.of(AiResponseDetailsDTO.DetectionDTO.builder()
                .id(9).label("plastic").confidence(.94f).x1(10).y1(20).x2(90).y2(180).build())).build();
    }
    DetailedAnalysisDTO response() {
        var r=new DetailedAnalysisDTO();r.setRequestId(7);r.setModelVersion("experiment-test");r.setExperimental(true);
        r.setStatus("COMPLETED");r.setImageWidth(100);r.setImageHeight(200);r.setComponentCount(1);
        var p=new DetailedAnalysisDTO.ParentDTO();p.setDetectionId(9);p.setComponentAnalysisStatus("COMPLETED");
        p.setComponents(List.of(AiResponseDetailsDTO.ComponentDTO.builder().partType("cap").material("metal")
            .detectionConfidence(.9f).materialConfidence(.8f).x1(30).y1(20).x2(60).y2(40).build()));
        r.setParents(List.of(p));return r;
    }
    @Test void detailedResultsNeverReplaceTheOriginalScan() {
        var scans=mock(ScanService.class);var model=mock(YoloClient.class);var original=scan();
        when(scans.detail(7)).thenReturn(original);when(model.predictDetailed(eq(7),anyString(),anyList())).thenReturn(response());
        var result=new DetailedAnalysisService(scans,model,mock(ComponentLearningService.class)).analyze(7);
        assertEquals(1,result.getComponentCount());assertEquals("Nắp chai",result.getParents().getFirst().getComponents().getFirst().getPartName());
        assertEquals("NEEDS_CONFIRM",result.getParents().getFirst().getComponents().getFirst().getStatus());
        assertEquals(.94f,original.getConfidenceAvg());assertEquals("plastic",original.getDetections().getFirst().getLabel());
        assertNull(original.getDetections().getFirst().getComponents());verify(scans,never()).predict(anyInt());
    }
    @Test void ownershipFailureStopsBeforeCallingTheModel() {
        var scans=mock(ScanService.class);var model=mock(YoloClient.class);
        when(scans.detail(7)).thenThrow(new ResponseStatusException(org.springframework.http.HttpStatus.FORBIDDEN));
        assertThrows(ResponseStatusException.class,()->new DetailedAnalysisService(scans,model,mock(ComponentLearningService.class)).analyze(7));verifyNoInteractions(model);
    }
    @Test void wrongParentOrOutsidePartIsRejectedWithoutRetryingLegacyScan() {
        for (boolean wrongParent:List.of(true,false)) {
            var scans=mock(ScanService.class);var model=mock(YoloClient.class);var r=response();
            if(wrongParent)r.getParents().getFirst().setDetectionId(88);else r.getParents().getFirst().getComponents().getFirst().setX1(0);
            when(scans.detail(7)).thenReturn(scan());when(model.predictDetailed(eq(7),anyString(),anyList())).thenReturn(r);
            var error=assertThrows(ResponseStatusException.class,()->new DetailedAnalysisService(scans,model,mock(ComponentLearningService.class)).analyze(7));
            assertEquals(503,error.getStatusCode().value());verify(scans,never()).predict(anyInt());
        }
    }
}
