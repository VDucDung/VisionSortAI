package com.example.hauiTrash.controller;

import com.example.hauiTrash.dto.AiResponseDetailsDTO;
import com.example.hauiTrash.dto.DetailedAnalysisDTO;
import com.example.hauiTrash.service.*;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import java.time.LocalDate;

@RestController
@RequestMapping("/api/v1/scans")
@RequiredArgsConstructor
public class ScanController {
    private final ScanService scans;
    private final ScanQueryService queries;
    private final DetailedAnalysisService detailed;
    @PostMapping(consumes = "multipart/form-data")
    public AiResponseDetailsDTO create(@RequestParam("file") MultipartFile file) { return scans.create(file); }
    @GetMapping("/{id}")
    public AiResponseDetailsDTO detail(@PathVariable Integer id) { return scans.detail(id); }
    @PostMapping("/{id}/retry")
    public AiResponseDetailsDTO retry(@PathVariable Integer id) { return scans.predict(id); }
    @PostMapping("/{id}/detailed")
    public DetailedAnalysisDTO detailed(@PathVariable Integer id) { return detailed.analyze(id); }
    @GetMapping
    public ScanQueryService.PageResult<ScanQueryService.ScanSummary> history(
        @RequestParam(defaultValue = "0") int page, @RequestParam(defaultValue = "12") int size,
        @RequestParam(required = false) String q, @RequestParam(required = false) String material,
        @RequestParam(required = false) LocalDate from, @RequestParam(required = false) LocalDate to) {
        return queries.history(false, page, size, q, material, from, to);
    }
}
