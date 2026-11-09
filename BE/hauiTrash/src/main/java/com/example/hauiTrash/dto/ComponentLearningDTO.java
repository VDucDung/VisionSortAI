package com.example.hauiTrash.dto;

import jakarta.validation.constraints.*;
import java.time.Instant;
import java.util.List;

public class ComponentLearningDTO {
    public record Feedback(
        @NotNull @Pattern(regexp="glass|metal|paper|plastic|unknown") String material,
        @NotNull @Pattern(regexp="PHYSICAL_CHECK|PACKAGING_MARK|VISUAL_ONLY|UNSURE") String verificationBasis,
        @NotNull Boolean regionCorrect,@NotNull Boolean trainingConsent,
        @Size(max=1000) String note,@NotNull @Min(0) Long revision) {}
    public record Review(@NotNull @Pattern(regexp="APPROVE|REJECT") String decision,
        @Size(max=1000) String note,@NotNull @Min(0) Long revision,
        @Pattern(regexp="PHYSICAL_CHECK|PACKAGING_MARK|VISUAL_REVIEW") String verificationBasis,Boolean confirmedCorrect) {}
    public record CaseView(String id,Integer scanId,Integer detectionId,String modelVersion,String imageUrl,
        Integer imageWidth,Integer imageHeight,String partType,String predictedMaterial,Float materialConfidence,
        Float detectionConfidence,Integer x1,Integer y1,Integer x2,Integer y2,Double priority,Boolean queryRecommended,
        String feedbackState,String humanMaterial,String verificationBasis,Boolean regionCorrect,Boolean trainingConsent,
        String humanNote,Instant submittedAt,String reviewNote,Instant reviewedAt,Long revision,String adminVerificationBasis) {}
    public record Queue(List<CaseView> items,long total,int page,int totalPages,long pending,long approved,long rejected) {}
}
