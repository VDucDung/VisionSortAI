package com.example.hauiTrash.service;

import com.example.hauiTrash.client.YoloClient;
import com.example.hauiTrash.dto.AiResponseDetailsDTO;
import com.example.hauiTrash.entity.*;
import com.example.hauiTrash.repository.AiRequestRepository;
import com.example.hauiTrash.security.CurrentAccount;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;
import java.time.Instant;
import java.util.*;

@Service
@RequiredArgsConstructor
public class ScanService {
    private final AiRequestRepository requests;
    private final CloudinaryService images;
    private final YoloClient model;
    private final CurrentAccount current;
    private final TransactionTemplate transactions;

    public AiResponseDetailsDTO create(MultipartFile file) {
        Account account = current.get();
        String imageUrl = images.uploadImage(file);
        AiRequest request = requests.save(AiRequest.builder().account(account).cloudinaryUrl(imageUrl)
                .status(RequestStatus.UPLOADED).build());
        return predict(request.getId());
    }

    public AiResponseDetailsDTO predict(Integer id) {
        AiRequest request = transactions.execute(tx -> {
            AiRequest found = requests.findForUpdate(id).orElseThrow(() -> missing());
            current.checkOwner(found);
            if (found.getFinishedAt() != null && found.getStatus() != RequestStatus.ERROR) return found;
            if (found.getStatus() == RequestStatus.PROCESSING && found.getProcessingAt() != null
                && found.getProcessingAt().isAfter(Instant.now().minusSeconds(300)))
                throw new ResponseStatusException(HttpStatus.CONFLICT, "Lượt quét đang được xử lý");
            found.setStatus(RequestStatus.PROCESSING);
            found.setProcessingAt(Instant.now());
            found.setErrorMessage(null);
            return requests.save(found);
        });
        if (request.getFinishedAt() != null && request.getStatus() != RequestStatus.PROCESSING) return detail(id);
        try {
            // Omit thresholds: the deployed AI configuration is the source of truth.
            var result = model.predictByImageUrl(id, request.getCloudinaryUrl());
            if (result.getDetections() == null)
                throw new IllegalStateException("Model response has no detections array");
            transactions.executeWithoutResult(tx -> {
                AiRequest saved = requests.findByIdWithDetections(id).orElseThrow(() -> missing());
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
                requests.save(saved);
            });
        } catch (Exception error) {
            transactions.executeWithoutResult(tx -> {
                AiRequest failed = requests.findById(id).orElseThrow(() -> missing());
                failed.setStatus(RequestStatus.ERROR);
                failed.setErrorMessage("Không thể phân tích ảnh. Hãy kiểm tra dịch vụ AI và thử lại.");
                requests.save(failed);
            });
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY,
                "Không thể phân tích ảnh. Lượt quét #" + id + " đã được lưu trong lịch sử để thử lại.");
        }
        return detail(id);
    }

    public AiResponseDetailsDTO detail(Integer id) {
        return transactions.execute(tx -> {
            AiRequest request = requests.findByIdWithDetections(id).orElseThrow(() -> missing());
            current.checkOwner(request);
            return toDetail(request);
        });
    }

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
                .components(d.getComponents().stream().map(ScanService::componentDetail).toList()).build();
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
    private static ResponseStatusException missing() { return new ResponseStatusException(HttpStatus.NOT_FOUND, "Không tìm thấy lượt quét"); }
}
