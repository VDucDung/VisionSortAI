package com.example.hauiTrash.exception;

import com.example.hauiTrash.dto.ApiResponse;
import org.springframework.http.*;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.*;

@RestControllerAdvice
public class ApiExceptionHandler {

    @ExceptionHandler(BadRequestException.class)
    public ResponseEntity<ApiResponse<Object>> badRequest(BadRequestException e) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(ApiResponse.builder().message(e.getMessage()).data(null).build());
    }

    @ExceptionHandler(UnauthorizedException.class)
    public ResponseEntity<ApiResponse<Object>> unauthorized(UnauthorizedException e) {
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                .body(ApiResponse.builder().message(e.getMessage()).data(null).build());
    }

    @ExceptionHandler(ForbiddenException.class)
    public ResponseEntity<ApiResponse<Object>> forbidden(ForbiddenException e) {
        return ResponseEntity.status(HttpStatus.FORBIDDEN)
                .body(ApiResponse.builder().message(e.getMessage()).data(null).build());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiResponse<Object>> validation(MethodArgumentNotValidException e) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(ApiResponse.builder().message(e.getBindingResult().getFieldErrors().stream()
                    .map(error -> error.getDefaultMessage()).findFirst().orElse("Dữ liệu không hợp lệ")).data(null).build());
    }

    @ExceptionHandler(org.springframework.web.server.ResponseStatusException.class)
    public ResponseEntity<ApiResponse<Object>> status(org.springframework.web.server.ResponseStatusException e) {
        return ResponseEntity.status(e.getStatusCode()).body(ApiResponse.builder().message(e.getReason()).build());
    }
    @ExceptionHandler(org.springframework.web.multipart.MaxUploadSizeExceededException.class)
    public ResponseEntity<ApiResponse<Object>> largeFile(Exception e) {
        return ResponseEntity.status(413).body(ApiResponse.builder().message("Ảnh vượt quá giới hạn 10 MB").build());
    }
    @ExceptionHandler(org.springframework.dao.DataIntegrityViolationException.class)
    public ResponseEntity<ApiResponse<Object>> conflict(Exception e) {
        return ResponseEntity.status(409).body(ApiResponse.builder().message("Dữ liệu bị trùng hoặc không hợp lệ").build());
    }
    @ExceptionHandler({org.springframework.web.method.annotation.MethodArgumentTypeMismatchException.class,
        org.springframework.http.converter.HttpMessageNotReadableException.class})
    public ResponseEntity<ApiResponse<Object>> malformed(Exception e) {
        return ResponseEntity.badRequest().body(ApiResponse.builder().message("Tham số hoặc nội dung yêu cầu không hợp lệ").build());
    }
}
