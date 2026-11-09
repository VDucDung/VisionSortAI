package com.example.hauiTrash.client;

import com.example.hauiTrash.dto.YoloPredictResponseDTO;
import com.example.hauiTrash.dto.DetailedAnalysisDTO;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import java.util.Map;
import java.util.List;

@Component
@RequiredArgsConstructor
public class YoloClient {

    private final RestTemplate restTemplate = timedClient();

    private static RestTemplate timedClient() {
        var factory = new org.springframework.http.client.SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(10000);
        factory.setReadTimeout(180000);
        return new RestTemplate(factory);
    }

    public YoloPredictResponseDTO predictByImageUrl(Integer requestId, String imageUrl) {
        return call(Map.of("request_id", requestId, "image_url", imageUrl));
    }

    @Value("${ai.yolo.base-url:http://127.0.0.1:8000}")
    private String baseUrl;

    @Value("${ai.components.base-url:}")
    private String componentsBaseUrl;

    public DetailedAnalysisDTO predictDetailed(Integer requestId, String imageUrl, List<Map<String, Integer>> parents) {
        String detailedBase = componentsBaseUrl == null || componentsBaseUrl.isBlank()
            ? baseUrl.replaceAll("/+$", "") + "/details" : componentsBaseUrl.replaceAll("/+$", "");
        var response = restTemplate.postForEntity(detailedBase + "/predict-image-url",
            Map.of("request_id", requestId, "image_url", imageUrl, "parents", parents), DetailedAnalysisDTO.class);
        if (!response.getStatusCode().is2xxSuccessful() || response.getBody() == null)
            throw new IllegalStateException("Detailed analysis unavailable");
        return response.getBody();
    }

    public YoloPredictResponseDTO predictByImageUrl(Integer requestId, String imageUrl, float conf, float iou) {
        Map<String, Object> body = Map.of(
                "request_id", requestId,
                "image_url", imageUrl,
                "conf", conf,
                "iou", iou
        );
        return call(body);
    }

    private YoloPredictResponseDTO call(Map<String, Object> body) {
        String url = baseUrl.replaceAll("/+$", "") + "/predict-image-url";

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        ResponseEntity<YoloPredictResponseDTO> res = restTemplate.exchange(
                url,
                HttpMethod.POST,
                new HttpEntity<>(body, headers),
                YoloPredictResponseDTO.class
        );

        if (!res.getStatusCode().is2xxSuccessful() || res.getBody() == null) {
            throw new RuntimeException("YOLO predict failed");
        }
        return res.getBody();
    }
}
