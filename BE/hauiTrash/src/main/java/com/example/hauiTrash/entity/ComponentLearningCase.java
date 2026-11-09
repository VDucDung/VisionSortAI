package com.example.hauiTrash.entity;

import jakarta.persistence.*;
import lombok.*;
import java.time.Instant;

/** Independent HITL record: predictions and the original scan are never relabelled. */
@Entity
@Table(name="component_learning_cases", indexes={@Index(name="idx_hitl_state_priority",columnList="feedback_state,priority,created_at")})
@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class ComponentLearningCase {
    @Id @Column(length=64) private String id;
    @ManyToOne(fetch=FetchType.LAZY,optional=false) @JoinColumn(name="scan_id",nullable=false) private AiRequest scan;
    @Column(nullable=false) private Integer detectionId;
    @Column(length=160,nullable=false) private String modelVersion;
    @Column(length=1000,nullable=false) private String imageUrl;
    @Column(nullable=false) private Integer imageWidth;
    @Column(nullable=false) private Integer imageHeight;
    @Column(length=16,nullable=false) private String partType;
    @Column(length=16,nullable=false) private String predictedMaterial;
    private Float detectionConfidence;
    private Float materialConfidence;
    private Integer x1;private Integer y1;private Integer x2;private Integer y2;
    @Column(nullable=false) private Double priority;
    @Column(nullable=false) private Boolean queryRecommended;
    @Column(name="feedback_state",length=16,nullable=false) private String feedbackState;
    @Column(length=16) private String humanMaterial;
    @Column(length=24) private String verificationBasis;
    private Boolean regionCorrect;
    private Boolean trainingConsent;
    @Column(length=1000) private String humanNote;
    @ManyToOne(fetch=FetchType.LAZY) @JoinColumn(name="submitted_by") private Account submittedBy;
    private Instant submittedAt;
    @ManyToOne(fetch=FetchType.LAZY) @JoinColumn(name="reviewed_by") private Account reviewedBy;
    private Instant reviewedAt;
    @Column(length=1000) private String reviewNote;
    @Column(length=24) private String adminVerificationBasis;
    @Column(name="created_at",nullable=false) private Instant createdAt;
    @Version private Long revision;
}
