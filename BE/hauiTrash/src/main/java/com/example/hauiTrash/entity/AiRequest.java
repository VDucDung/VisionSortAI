package com.example.hauiTrash.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "ai_requests")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class AiRequest {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "account_id")
    private Account account;

    @Column(name = "cloudinary_url", length = 1000)
    private String cloudinaryUrl;

    @Column(name = "created_at")
    private Instant createdAt;

    @Column(name = "finished_at")
    private Instant finishedAt;

    @Enumerated(EnumType.STRING)
    @Column(length = 20)
    private RequestStatus status;

    @Column(length = 500)
    private String errorMessage;

    @Column(length = 1000)
    private String annotatedUrl;

    private Instant processingAt;

    @Column(length = 30)
    private String analysisMode;

    @Column(length = 160)
    private String componentModelVersion;

    @OneToMany(mappedBy = "aiRequest", cascade = CascadeType.ALL, orphanRemoval = true)
    @Builder.Default
    private List<Detection> detections = new ArrayList<>();

    @PrePersist
    void prePersist() {
        if (createdAt == null) {
            createdAt = Instant.now();
        }
    }
}
