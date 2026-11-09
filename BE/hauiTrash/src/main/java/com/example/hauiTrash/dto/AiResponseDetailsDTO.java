package com.example.hauiTrash.dto;

import lombok.*;

import java.time.Instant;
import java.util.List;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class AiResponseDetailsDTO {

    private Integer id;
    private String cloudinaryUrl;
    private Instant createdAt;
    private Instant finishedAt;
    private Integer accountId;
    private com.example.hauiTrash.entity.RequestStatus status;
    private String errorMessage;

    private boolean requiresConfirmation;

    private String annotatedUrl;
    private Integer count;
    private Float confidenceAvg;

    private List<DetectionDTO> detections;
    private String analysisMode;
    private String componentModelVersion;
    private Integer componentCount;

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    @Builder
    public static class DetectionDTO {
        private Integer id;
        private String label;
        private String labelDisplay;
        private Float confidence;
        private String annotatedUrl;

        private Integer trashItemId;
        private String status;

        // thêm cho crop preview
        private Integer x1;
        private Integer y1;
        private Integer x2;
        private Integer y2;
        private String cropUrl;

        private String trashType;
        private String material;
        private String note;
        private String action;

        private DetailDTO detail;
        private Integer quantity;
        private String binCode;
        private String binName;
        private String binColorCode;
        private String componentAnalysisStatus;
        private List<ComponentDTO> components;
    }

    @Data @NoArgsConstructor @AllArgsConstructor @Builder
    public static class ComponentDTO {
        private String learningCaseId;
        private Boolean queryRecommended;
        private Double queryPriority;
        private String feedbackState;
        private String humanMaterial;
        private Long feedbackRevision;
        private Integer id;
        private String partType;
        private String partName;
        private String material;
        private String materialName;
        private Float detectionConfidence;
        private Float materialConfidence;
        private String status;
        private Integer x1;
        private Integer y1;
        private Integer x2;
        private Integer y2;
        private String action;
        private String binName;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    @Builder
    public static class DetailDTO {
        private String impact;
        private String toxicity;
        private List<String> safeSteps;
        private List<TrashStepDTO> trashSteps;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    @Builder
    public static class TrashStepDTO {
        private Long id;
        private String label;
        private String labelDisplay;
        private String imageUrl;
    }
}
