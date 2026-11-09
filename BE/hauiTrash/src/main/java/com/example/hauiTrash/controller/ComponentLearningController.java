package com.example.hauiTrash.controller;
import com.example.hauiTrash.dto.ComponentLearningDTO.*;
import com.example.hauiTrash.dto.ComponentLearningDTO.Queue;
import com.example.hauiTrash.service.ComponentLearningService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import java.util.*;

@RestController @RequiredArgsConstructor
public class ComponentLearningController {
    private final ComponentLearningService learning;
    @GetMapping("/api/v1/scans/{scanId}/learning")
    public List<CaseView> cases(@PathVariable Integer scanId){return learning.forScan(scanId);}
    @PostMapping("/api/v1/scans/{scanId}/learning/{caseId}/feedback")
    public CaseView feedback(@PathVariable Integer scanId,@PathVariable String caseId,@Valid @RequestBody Feedback body){return learning.feedback(scanId,caseId,body);}
    @GetMapping("/api/v1/admin/learning")
    public Queue queue(@RequestParam(defaultValue="PENDING") String state,@RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="20") int size){return learning.queue(state,page,size);}
    @PostMapping("/api/v1/admin/learning/{caseId}/review")
    public CaseView review(@PathVariable String caseId,@Valid @RequestBody Review body){return learning.review(caseId,body);}
    @GetMapping("/api/v1/admin/learning/export")
    public Map<String,Object> export(@RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="100") int size){return learning.export(page,size);}
}
