package com.example.hauiTrash.service.impl;

import com.example.hauiTrash.dto.UserPointsDTO;
import com.example.hauiTrash.entity.PointHistory;
import com.example.hauiTrash.entity.UserPoints;
import com.example.hauiTrash.entity.UserRank;
import com.example.hauiTrash.repository.AccountRepository;
import com.example.hauiTrash.repository.PointHistoryRepository;
import com.example.hauiTrash.repository.UserPointsRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class PointServiceImplTest {

    @Mock
    private UserPointsRepository userPointsRepository;

    @Mock
    private PointHistoryRepository pointHistoryRepository;

    @Mock
    private AccountRepository accountRepository;

    @InjectMocks
    private PointServiceImpl pointService;

    @Test
    void getUserPointsReturnsBronzeRankWhenNoRecordExists() {
        when(userPointsRepository.findByAccountId(12)).thenReturn(Optional.empty());

        UserPointsDTO result = pointService.getUserPoints(12);

        assertEquals(0, result.getTotalPoints());
        assertEquals(UserRank.BRONZE, result.getRank());
        assertEquals(UserRank.BRONZE.getDisplayName(), result.getRankDisplayName());
    }

    @Test
    void addPointsPersistsHistoryAndUpdatedTotal() {
        when(userPointsRepository.findByAccountId(12)).thenReturn(Optional.empty());

        pointService.addPoints(12, "DETECTION_PLASTIC", "detection-1", "Plastic bottle");

        ArgumentCaptor<PointHistory> historyCaptor = ArgumentCaptor.forClass(PointHistory.class);
        verify(pointHistoryRepository).save(historyCaptor.capture());
        assertEquals(12, historyCaptor.getValue().getAccountId());
        assertEquals(1, historyCaptor.getValue().getPoints());
        assertEquals("detection-1", historyCaptor.getValue().getReferenceId());

        ArgumentCaptor<UserPoints> pointsCaptor = ArgumentCaptor.forClass(UserPoints.class);
        verify(userPointsRepository).save(pointsCaptor.capture());
        assertEquals(1, pointsCaptor.getValue().getTotalPoints());
        assertEquals(12, pointsCaptor.getValue().getAccountId());
    }

    @Test
    void addPointsSkipsDuplicateReference() {
        when(pointHistoryRepository.existsByAccountIdAndActionTypeAndReferenceId(
                12, "DETECTION_PLASTIC", "detection-1")).thenReturn(true);

        pointService.addPoints(12, "DETECTION_PLASTIC", "detection-1", "Plastic bottle");

        verify(pointHistoryRepository, never()).save(org.mockito.ArgumentMatchers.any(PointHistory.class));
        verifyNoInteractions(userPointsRepository);
    }

    @Test
    void addPointsIgnoresUnknownActionType() {
        pointService.addPoints(12, "UNKNOWN_ACTION", null, "ignored");

        verifyNoInteractions(userPointsRepository, pointHistoryRepository, accountRepository);
    }

    @Test
    void getLeaderboardUsesUnknownNameWhenAccountIsMissing() {
        when(userPointsRepository.findTopLeaderboard(any(Pageable.class)))
                .thenReturn(java.util.List.of(UserPoints.builder().accountId(12).totalPoints(100).build()));
        when(accountRepository.findById(12)).thenReturn(Optional.empty());

        var result = pointService.getLeaderboard(PageRequest.of(0, 10));

        assertEquals(1, result.size());
        assertEquals("Unknown", result.get(0).getFullName());
        assertNull(result.get(0).getAvatarUrl());
    }
}