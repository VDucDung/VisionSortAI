package com.example.hauiTrash.controller;

import org.springframework.web.bind.annotation.*;
import java.util.Map;

/** Public capability marker so the frontend can detect an obsolete running process. */
@RestController
@RequestMapping("/api/v1/system")
public class SystemInfoController {
    @GetMapping("/info")
    public Map<String,Object> info() {
        return Map.of("application", "TrashSmart", "scanApiVersion", 1,
            "release", "20261107-hitl", "preservesErrorStatus", true, "adminProfileApiVersion", 1,
            "componentsApiVersion", 1, "detailedAnalysisApiVersion", 1, "hitlApiVersion", 1);
    }
}
