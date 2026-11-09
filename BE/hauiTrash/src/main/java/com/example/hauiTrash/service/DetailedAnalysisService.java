package com.example.hauiTrash.service;

import com.example.hauiTrash.client.YoloClient;
import com.example.hauiTrash.dto.*;
import com.example.hauiTrash.entity.RequestStatus;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import java.util.*;

/** On-demand analysis with independent HITL snapshots; the original scan stays intact. */
@Service
@RequiredArgsConstructor
@Slf4j
public class DetailedAnalysisService {
    private final ScanService scans;
    private final YoloClient model;
    private final ComponentLearningService learning;

    public DetailedAnalysisDTO analyze(Integer id) {
        // Includes the existing owner/admin check before any image is sent to AI.
        var scan = scans.detail(id);
        if (scan.getStatus() != RequestStatus.DONE || scan.getDetections() == null || scan.getDetections().isEmpty())
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Cần có kết quả nhận diện chai trước khi phân tích chi tiết.");
        if (scan.getDetections().size() > 30)
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Ảnh có quá nhiều vật thể. Hãy chọn ảnh có ít chai hơn.");
        Map<Integer, AiResponseDetailsDTO.DetectionDTO> expected = new HashMap<>();
        List<Map<String, Integer>> parents = new ArrayList<>();
        for (var d : scan.getDetections()) {
            if (d.getId() == null || d.getX1() == null || d.getY1() == null || d.getX2() == null || d.getY2() == null
                || d.getX1() < 0 || d.getY1() < 0 || d.getX2() <= d.getX1() || d.getY2() <= d.getY1())
                throw new ResponseStatusException(HttpStatus.CONFLICT, "Lượt quét cũ chưa lưu đủ tọa độ. Hãy quét ảnh mới để xem chi tiết.");
            expected.put(d.getId(), d);
            parents.add(Map.of("id", d.getId(), "x1", d.getX1(), "y1", d.getY1(), "x2", d.getX2(), "y2", d.getY2()));
        }
        try {
            var result = model.predictDetailed(id, scan.getCloudinaryUrl(), parents);
            validate(id, expected, result);
            learning.attachCases(scan, result);
            result.setNotice("Nhận diện chi tiết đang thử nghiệm. Kiểm tra trực tiếp vật liệu trước khi phân loại.");
            return result;
        } catch (Exception error) {
            // Keep URLs, credentials and upstream response bodies out of logs.
            log.warn("Detailed analysis failed for scan {}: {}", id, error.getClass().getSimpleName());
            String reason = "Chưa phân tích chi tiết được. Kiểm tra dịch vụ model chi tiết; kết quả nhận diện cũ vẫn được giữ.";
            if (error instanceof org.springframework.web.client.ResourceAccessException)
                reason = "Không kết nối được dịch vụ AI chi tiết. Hãy khởi động lại AI; kết quả nhận diện cũ vẫn được giữ.";
            else if (error instanceof org.springframework.web.client.HttpClientErrorException.NotFound)
                reason = "AI đang chạy bản chưa hỗ trợ nhận diện chi tiết. Hãy khởi động lại AI sau khi cập nhật.";
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                reason);
        }
    }

    private static void validate(Integer id, Map<Integer, AiResponseDetailsDTO.DetectionDTO> expected, DetailedAnalysisDTO r) {
        if (r == null || !id.equals(r.getRequestId()) || !"COMPLETED".equals(r.getStatus())
            || !Boolean.TRUE.equals(r.getExperimental()) || r.getModelVersion() == null || r.getModelVersion().length() > 160
            || r.getParents() == null || r.getParents().size() != expected.size()
            || r.getImageWidth() == null || r.getImageHeight() == null || r.getImageWidth() < 1 || r.getImageHeight() < 1
            || r.getImageWidth() > 8192 || r.getImageHeight() > 8192 || (long)r.getImageWidth()*r.getImageHeight() > 12_000_000)
            throw new IllegalStateException("Invalid detailed response");
        Set<Integer> seen = new HashSet<>(); int count = 0;
        for (var parent : r.getParents()) {
            var d = expected.get(parent.getDetectionId());
            if (d == null || !seen.add(parent.getDetectionId()) || !"COMPLETED".equals(parent.getComponentAnalysisStatus())
                || parent.getComponents() == null || parent.getComponents().size() > 30
                || d.getX2() > r.getImageWidth() || d.getY2() > r.getImageHeight())
                throw new IllegalStateException("Invalid detailed parent");
            for (var c : parent.getComponents()) {
                if (c.getPartType() == null || !Set.of("cap", "body", "label").contains(c.getPartType())
                    || c.getMaterial() == null || !Set.of("glass", "metal", "paper", "plastic", "unknown").contains(c.getMaterial())
                    || !confidence(c.getDetectionConfidence()) || !confidence(c.getMaterialConfidence())
                    || c.getX1() == null || c.getY1() == null || c.getX2() == null || c.getY2() == null
                    || c.getX1() < d.getX1() || c.getY1() < d.getY1() || c.getX2() > d.getX2() || c.getY2() > d.getY2()
                    || c.getX2() <= c.getX1() || c.getY2() <= c.getY1()) throw new IllegalStateException("Invalid component");
                c.setPartName(switch (c.getPartType()) { case "cap" -> "Nắp chai"; case "body" -> "Thân/vỏ chai"; default -> "Nhãn dán"; });
                var material = MaterialCatalog.find(c.getMaterial());
                c.setMaterialName(material == null ? "Chưa xác định" : material.name());
                c.setStatus("NEEDS_CONFIRM");
                c.setAction(material == null ? "Chưa đủ tin cậy để xác định vật liệu. Hãy kiểm tra trực tiếp."
                    : "Tách bộ phận khi có thể và kiểm tra lại vật liệu trước khi thu gom.");
                count++;
            }
        }
        if (r.getComponentCount() == null || r.getComponentCount() != count) throw new IllegalStateException("Invalid component count");
    }

    private static boolean confidence(Float value) { return value != null && Float.isFinite(value) && value >= 0 && value <= 1; }
}
