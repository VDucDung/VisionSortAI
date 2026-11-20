package com.example.hauiTrash.mapper;

import com.example.hauiTrash.dto.AiResponseDetailsDTO;
import com.example.hauiTrash.entity.*;
import com.example.hauiTrash.service.MaterialCatalog;
import java.util.Locale;
import java.util.Objects;
import org.springframework.stereotype.Component;

/** Builds scan responses without database access or AI side effects. */
@Component
public class ScanResponseMapper {
    public AiResponseDetailsDTO toDetail(AiRequest request) {
        var detections = request.getDetections().stream().map(d -> {
            var material = MaterialCatalog.find(d.getLabel());
            return AiResponseDetailsDTO.DetectionDTO.builder().id(d.getId()).label(d.getLabel())
                .labelDisplay(d.getLabelDisplay()).confidence(d.getConfidence()).status(d.getStatus())
                .annotatedUrl(d.getAnnotatedUrl()).cropUrl(d.getCropUrl())
                .x1(d.getX1()).y1(d.getY1()).x2(d.getX2()).y2(d.getY2()).quantity(1)
                .material(material == null ? null : material.name()).trashType(material == null ? "Chưa xác định" : "Có thể tái chế")
                .binCode(material == null ? null : material.code()).binName(material == null ? "Cần kiểm tra thêm" : "Thu gom " + material.name().toLowerCase(Locale.ROOT))
                .binColorCode(material == null ? "#718096" : material.color())
                .action(material == null ? "Chưa có hướng dẫn cho vật liệu này. Hãy kiểm tra thủ công." : material.guidance())
                .componentAnalysisStatus(d.getComponentAnalysisStatus() == null ? "NOT_RUN" : d.getComponentAnalysisStatus())
                .components(d.getComponents().stream().map(ScanResponseMapper::componentDetail).toList()).build();
        }).toList();
        String annotated = request.getAnnotatedUrl();
        if (annotated == null) annotated = detections.stream().map(AiResponseDetailsDTO.DetectionDTO::getAnnotatedUrl)
            .filter(Objects::nonNull).findFirst().orElse(null);
        return AiResponseDetailsDTO.builder().id(request.getId()).accountId(request.getAccount() == null ? null : request.getAccount().getId())
            .cloudinaryUrl(request.getCloudinaryUrl()).annotatedUrl(annotated).createdAt(request.getCreatedAt()).finishedAt(request.getFinishedAt())
            .status(status(request)).errorMessage(request.getErrorMessage()).count(detections.size())
            .requiresConfirmation(detections.stream().anyMatch(d -> "NEEDS_CONFIRM".equals(d.getStatus()) || d.getComponents().stream().anyMatch(c -> "NEEDS_CONFIRM".equals(c.getStatus()))))
            .confidenceAvg((float) detections.stream().filter(d -> d.getConfidence() != null).mapToDouble(d -> d.getConfidence()).average().orElse(0))
            .analysisMode(request.getAnalysisMode() == null ? "bottle" : request.getAnalysisMode())
            .componentModelVersion(request.getComponentModelVersion())
            .componentCount(detections.stream().mapToInt(d -> d.getComponents().size()).sum()).detections(detections).build();
    }

    private static AiResponseDetailsDTO.ComponentDTO componentDetail(DetectionComponent c) {
        var material = MaterialCatalog.find(c.getMaterial());
        boolean uncertain = material == null || "NEEDS_CONFIRM".equals(c.getStatus());
        String partName = switch(c.getPartType()) { case "cap" -> "Nắp chai"; case "body" -> "Thân/vỏ chai"; default -> "Nhãn dán"; };
        return AiResponseDetailsDTO.ComponentDTO.builder().id(c.getId()).partType(c.getPartType()).partName(partName)
            .material(c.getMaterial()).materialName(material == null ? "Chưa xác định" : material.name())
            .detectionConfidence(c.getDetectionConfidence()).materialConfidence(c.getMaterialConfidence()).status(c.getStatus())
            .x1(c.getX1()).y1(c.getY1()).x2(c.getX2()).y2(c.getY2())
            .binName(uncertain ? "Cần kiểm tra vật liệu" : "Thu gom " + material.name().toLowerCase(Locale.ROOT))
            .action(uncertain ? "Kiểm tra trực tiếp vật liệu của bộ phận này trước khi phân loại." : material.guidance()).build();
    }

    public static RequestStatus status(AiRequest request) {
        return request.getStatus() != null ? request.getStatus() : request.getFinishedAt() != null ? RequestStatus.DONE : RequestStatus.UPLOADED;
    }
}
