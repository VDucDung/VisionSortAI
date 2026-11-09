package com.example.hauiTrash.repository;

import com.example.hauiTrash.entity.ComponentLearningCase;
import org.springframework.data.jpa.repository.*;
import org.springframework.data.repository.query.Param;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import java.util.*;

public interface ComponentLearningCaseRepository extends JpaRepository<ComponentLearningCase,String> {
    @Lock(jakarta.persistence.LockModeType.PESSIMISTIC_WRITE)
    @Query("select c from ComponentLearningCase c where c.id=:id")
    Optional<ComponentLearningCase> findLocked(@Param("id") String id);
    Page<ComponentLearningCase> findByFeedbackState(String state,Pageable pageable);
    long countByFeedbackState(String state);
    List<ComponentLearningCase> findByScanIdOrderByPriorityDesc(Integer id);
    Page<ComponentLearningCase> findByFeedbackStateAndTrainingConsentTrueAndRegionCorrectTrue(String state,Pageable pageable);
}
