package com.example.hauiTrash.dto;

import lombok.Data;
import java.util.List;

@Data
public class DetailedAnalysisDTO {
    private Integer requestId;
    private String modelVersion;
    private Boolean experimental;
    private String status;
    private Integer imageWidth;
    private Integer imageHeight;
    private Integer componentCount;
    private String notice;
    private List<ParentDTO> parents;

    @Data
    public static class ParentDTO {
        private Integer detectionId;
        private String componentAnalysisStatus;
        private List<AiResponseDetailsDTO.ComponentDTO> components;
    }
}
