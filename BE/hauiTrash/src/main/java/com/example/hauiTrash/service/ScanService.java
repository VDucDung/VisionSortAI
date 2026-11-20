package com.example.hauiTrash.service;

import com.example.hauiTrash.client.YoloClient;
import com.example.hauiTrash.dto.AiResponseDetailsDTO;
import com.example.hauiTrash.entity.*;
import com.example.hauiTrash.mapper.ScanPredictionMapper;
import com.example.hauiTrash.mapper.ScanResponseMapper;
import com.example.hauiTrash.repository.AiRequestRepository;
import com.example.hauiTrash.security.CurrentAccount;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;
import java.time.Instant;

@Service
@RequiredArgsConstructor
public class ScanService {
    private final AiRequestRepository requests;
    private final CloudinaryService images;
    private final YoloClient model;
    private final CurrentAccount current;
    private final TransactionTemplate transactions;
    private final ScanPredictionMapper predictionMapper;
    private final ScanResponseMapper responseMapper;

    public AiResponseDetailsDTO create(MultipartFile file) {
        Account account = current.get();
        String imageUrl = images.uploadImage(file);
        AiRequest request = requests.save(AiRequest.builder().account(account).cloudinaryUrl(imageUrl)
                .status(RequestStatus.UPLOADED).build());
        return predict(request.getId());
    }

    public AiResponseDetailsDTO predict(Integer id) {
        AiRequest request = transactions.execute(tx -> {
            AiRequest found = requests.findForUpdate(id).orElseThrow(() -> missing());
            current.checkOwner(found);
            if (found.getFinishedAt() != null && found.getStatus() != RequestStatus.ERROR) return found;
            if (found.getStatus() == RequestStatus.PROCESSING && found.getProcessingAt() != null
                && found.getProcessingAt().isAfter(Instant.now().minusSeconds(300)))
                throw new ResponseStatusException(HttpStatus.CONFLICT, "Lượt quét đang được xử lý");
            found.setStatus(RequestStatus.PROCESSING);
            found.setProcessingAt(Instant.now());
            found.setErrorMessage(null);
            return requests.save(found);
        });
        if (request.getFinishedAt() != null && request.getStatus() != RequestStatus.PROCESSING) return detail(id);
        try {
            // Omit thresholds: the deployed AI configuration is the source of truth.
            var result = model.predictByImageUrl(id, request.getCloudinaryUrl());
            if (result.getDetections() == null)
                throw new IllegalStateException("Model response has no detections array");
            transactions.executeWithoutResult(tx -> {
                AiRequest saved = requests.findByIdWithDetections(id).orElseThrow(() -> missing());
                predictionMapper.apply(saved, result);
                requests.save(saved);
            });
        } catch (Exception error) {
            transactions.executeWithoutResult(tx -> {
                AiRequest failed = requests.findById(id).orElseThrow(() -> missing());
                failed.setStatus(RequestStatus.ERROR);
                failed.setErrorMessage("Không thể phân tích ảnh. Hãy kiểm tra dịch vụ AI và thử lại.");
                requests.save(failed);
            });
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY,
                "Không thể phân tích ảnh. Lượt quét #" + id + " đã được lưu trong lịch sử để thử lại.");
        }
        return detail(id);
    }

    public AiResponseDetailsDTO detail(Integer id) {
        return transactions.execute(tx -> {
            AiRequest request = requests.findByIdWithDetections(id).orElseThrow(() -> missing());
            current.checkOwner(request);
            return toDetail(request);
        });
    }

    public AiResponseDetailsDTO toDetail(AiRequest request) {
        return responseMapper.toDetail(request);
    }

    public static RequestStatus status(AiRequest request) {
        return ScanResponseMapper.status(request);
    }
    private static ResponseStatusException missing() { return new ResponseStatusException(HttpStatus.NOT_FOUND, "Không tìm thấy lượt quét"); }
}
