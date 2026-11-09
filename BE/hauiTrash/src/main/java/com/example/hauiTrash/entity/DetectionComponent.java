package com.example.hauiTrash.entity;

import jakarta.persistence.*;
import lombok.*;

/** A visible part of one bottle; it is not another whole-object detection. */
@Entity
@Table(name = "detection_components", indexes = @Index(name = "idx_component_detection", columnList = "detection_id"))
@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class DetectionComponent {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "detection_id", nullable = false)
    private Detection detection;
    @Column(nullable = false, length = 20)
    private String partType;
    @Column(nullable = false, length = 20)
    private String material;
    private Float detectionConfidence;
    private Float materialConfidence;
    @Column(nullable = false, length = 30)
    private String status;
    private Integer x1;
    private Integer y1;
    private Integer x2;
    private Integer y2;
}
