package com.example.hauiTrash.service.impl;

import com.example.hauiTrash.dto.TrashBinDTO;
import com.example.hauiTrash.entity.TrashBin;
import com.example.hauiTrash.mapper.TrashBinMapper;
import com.example.hauiTrash.repository.TrashBinRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class TrashBinServiceImplTest {

    @Mock
    private TrashBinRepository trashBinRepository;

    @Mock
    private TrashBinMapper trashBinMapper;

    @InjectMocks
    private TrashBinServiceImpl trashBinService;

    @Test
    void getAllTrashBinsMapsRepositoryResults() {
        TrashBin bin = TrashBin.builder().id(1L).code("paper").build();
        TrashBinDTO dto = new TrashBinDTO();
        when(trashBinRepository.findAll()).thenReturn(List.of(bin));
        when(trashBinMapper.toDTO(bin)).thenReturn(dto);

        List<TrashBinDTO> result = trashBinService.getAllTrashBins();

        assertEquals(List.of(dto), result);
        verify(trashBinMapper).toDTO(bin);
    }

    @Test
    void getActiveTrashBinsUsesActiveRepositoryQuery() {
        TrashBin bin = TrashBin.builder().id(2L).code("plastic").build();
        TrashBinDTO dto = new TrashBinDTO();
        when(trashBinRepository.findAllByIsActiveTrue()).thenReturn(List.of(bin));
        when(trashBinMapper.toDTO(bin)).thenReturn(dto);

        List<TrashBinDTO> result = trashBinService.getActiveTrashBins();

        assertEquals(List.of(dto), result);
        verify(trashBinRepository).findAllByIsActiveTrue();
    }

    @Test
    void getTrashBinByIdThrowsWhenBinIsMissing() {
        when(trashBinRepository.findById(99L)).thenReturn(Optional.empty());

        assertThrows(RuntimeException.class, () -> trashBinService.getTrashBinById(99L));

        verifyNoInteractions(trashBinMapper);
    }

    @Test
    void getTrashBinByNameMapsMatchingBin() {
        TrashBin bin = TrashBin.builder().id(3L).code("glass").build();
        TrashBinDTO dto = new TrashBinDTO();
        when(trashBinRepository.findByCode("glass")).thenReturn(Optional.of(bin));
        when(trashBinMapper.toDTO(bin)).thenReturn(dto);

        assertSame(dto, trashBinService.getTrashBinByName("glass"));
    }

    @Test
    void createTrashBinDefaultsToActiveWhenMapperLeavesStatusNull() {
        TrashBinDTO input = new TrashBinDTO();
        input.setCode("metal");
        TrashBin bin = TrashBin.builder().code("metal").isActive(null).build();
        TrashBinDTO output = new TrashBinDTO();
        when(trashBinRepository.existsByCode("metal")).thenReturn(false);
        when(trashBinMapper.toEntity(input)).thenReturn(bin);
        when(trashBinRepository.save(bin)).thenReturn(bin);
        when(trashBinMapper.toDTO(bin)).thenReturn(output);

        TrashBinDTO result = trashBinService.createTrashBin(input);

        assertTrue(bin.getIsActive());
        assertSame(output, result);
    }

    @Test
    void createTrashBinRejectsDuplicateCodeBeforeMapping() {
        TrashBinDTO input = new TrashBinDTO();
        input.setCode("paper");
        when(trashBinRepository.existsByCode("paper")).thenReturn(true);

        assertThrows(RuntimeException.class, () -> trashBinService.createTrashBin(input));

        verifyNoInteractions(trashBinMapper);
        verify(trashBinRepository, never()).save(org.mockito.ArgumentMatchers.any(TrashBin.class));
    }

    @Test
    void updateTrashBinPreservesCurrentStatusWhenInputStatusIsNull() {
        TrashBin bin = TrashBin.builder().id(4L).code("paper").isActive(false).build();
        TrashBinDTO input = new TrashBinDTO();
        input.setNameTrash("Paper bin");
        input.setCode("paper");
        input.setDescription("Paper recycling");
        TrashBinDTO output = new TrashBinDTO();
        when(trashBinRepository.findById(4L)).thenReturn(Optional.of(bin));
        when(trashBinRepository.save(bin)).thenReturn(bin);
        when(trashBinMapper.toDTO(bin)).thenReturn(output);

        TrashBinDTO result = trashBinService.updateTrashBin(4L, input);

        assertSame(output, result);
        assertEquals("Paper bin", bin.getNameTrash());
        assertEquals("Paper recycling", bin.getDescription());
        assertEquals(false, bin.getIsActive());
    }

    @Test
    void updateTrashBinRejectsCodeOwnedByAnotherBin() {
        TrashBin bin = TrashBin.builder().id(5L).code("paper").build();
        TrashBinDTO input = new TrashBinDTO();
        input.setCode("plastic");
        when(trashBinRepository.findById(5L)).thenReturn(Optional.of(bin));
        when(trashBinRepository.existsByCode("plastic")).thenReturn(true);

        assertThrows(RuntimeException.class, () -> trashBinService.updateTrashBin(5L, input));

        verify(trashBinRepository, never()).save(org.mockito.ArgumentMatchers.any(TrashBin.class));
    }

    @Test
    void deleteTrashBinDeletesExistingBin() {
        TrashBin bin = TrashBin.builder().id(6L).build();
        when(trashBinRepository.findById(6L)).thenReturn(Optional.of(bin));

        trashBinService.deleteTrashBin(6L);

        verify(trashBinRepository).delete(bin);
    }
}