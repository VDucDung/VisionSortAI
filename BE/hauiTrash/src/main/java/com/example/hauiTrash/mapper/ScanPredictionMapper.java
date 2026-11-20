package com.example.hauiTrash.mapper;

import com.example.hauiTrash.dto.YoloPredictResponseDTO;
import com.example.hauiTrash.entity.*;
import com.example.hauiTrash.service.MaterialCatalog;
import java.time.Instant;
import java.util.Set;
import org.springframework.stereotype.Component;

/** Validates the AI contract and applies predictions inside the caller's transaction. */
@Component
public class ScanPredictionMapper {
    public void apply(AiRequest saved, YoloPredictResponseDTO result) {
        saved.getDetections().clear();
        for (var detection : result.getDetections()) {
            Float confidence = detection.getConfidence();
            if (confidence == null || !Float.isFinite(confidence) || confidence < 0 || confidence > 1)
                throw new IllegalStateException("Model confidence must be in [0,1]");
            var material = MaterialCatalog.find(detection.getLabel());
            var entity = Detection.builder().aiRequest(saved)
                .label(material == null ? detection.getLabel() : material.code())
                .labelDisplay(detection.getLabelDisplay() == null ? (material == null ? "Chưa xác định" : material.name()) : detection.getLabelDisplay())
                .confidence(confidence).annotatedUrl(result.getAnnotatedUrl()).cropUrl(detection.getCropUrl())
                .x1(detection.getX1()).y1(detection.getY1()).x2(detection.getX2()).y2(detection.getY2())
                .status(material == null || Boolean.TRUE.equals(detection.getNeedsConfirm()) ? "NEEDS_CONFIRM" : "DETECTED").build();
            attachComponents(entity, detection);
            saved.getDetections().add(entity);
        }
        if (result.getComponentsApiVersion() != null && result.getComponentsApiVersion() != 1)
            throw new IllegalStateException("Unsupported component API version");
        String version = result.getComponentModelVersion();
        if (version != null && version.length() > 160) throw new IllegalStateException("Model version too long");
        saved.setAnalysisMode(saved.getDetections().stream().anyMatch(d -> "COMPLETED".equals(d.getComponentAnalysisStatus())) ? "bottle_components" : "bottle");
        saved.setComponentModelVersion(version);
        saved.setAnnotatedUrl(result.getAnnotatedUrl());
        saved.setFinishedAt(Instant.now());
        saved.setStatus(RequestStatus.DONE);
    }

    private static void attachComponents(Detection parent, com.example.hauiTrash.dto.YoloPredictResponseDTO.DetectionDTO source) {
        String status = source.getComponentAnalysisStatus() == null ? "NOT_RUN" : source.getComponentAnalysisStatus();
        if (!Set.of("NOT_RUN", "MODEL_UNAVAILABLE", "COMPLETED", "FAILED").contains(status))
            throw new IllegalStateException("Invalid component analysis status");
        var components = source.getComponents();
        if (components != null && !components.isEmpty() && !"COMPLETED".equals(status))
            throw new IllegalStateException("Uncompleted component analysis cannot contain predictions");
        if (components != null && components.size() > 30) throw new IllegalStateException("Too many components per bottle");
        parent.setComponentAnalysisStatus(status);
        if (components == null) return;
        for (var c : components) {
            if (c == null || c.getPartType() == null || !Set.of("cap", "body", "label").contains(c.getPartType()))
                throw new IllegalStateException("Invalid component type");
            if (c.getMaterial() == null || !Set.of("glass", "metal", "paper", "plastic", "unknown").contains(c.getMaterial()))
                throw new IllegalStateException("Invalid component material");
            validConfidence(c.getDetectionConfidence()); validConfidence(c.getMaterialConfidence());
            if (c.getX1() == null || c.getY1() == null || c.getX2() == null || c.getY2() == null
                || parent.getX1() == null || parent.getY1() == null || parent.getX2() == null || parent.getY2() == null
                || c.getX1() < parent.getX1() || c.getY1() < parent.getY1() || c.getX2() > parent.getX2() || c.getY2() > parent.getY2()
                || c.getX1() < 0 || c.getY1() < 0 || c.getX1() >= c.getX2() || c.getY1() >= c.getY2())
                throw new IllegalStateException("Component bbox must be inside its parent bottle");
            parent.getComponents().add(DetectionComponent.builder().detection(parent).partType(c.getPartType()).material(c.getMaterial())
                .detectionConfidence(c.getDetectionConfidence()).materialConfidence(c.getMaterialConfidence())
                .x1(c.getX1()).y1(c.getY1()).x2(c.getX2()).y2(c.getY2())
                .status("unknown".equals(c.getMaterial()) || Boolean.TRUE.equals(c.getNeedsConfirm()) ? "NEEDS_CONFIRM" : "DETECTED").build());
        }
    }

    private static void validConfidence(Float value) {
        if (value == null || !Float.isFinite(value) || value < 0 || value > 1)
            throw new IllegalStateException("Component confidence must be in [0,1]");
    }
}
