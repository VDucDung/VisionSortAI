package com.example.hauiTrash.service;

import com.example.hauiTrash.entity.*;
import com.example.hauiTrash.repository.*;
import com.example.hauiTrash.security.CurrentAccount;
import jakarta.persistence.EntityManager;
import jakarta.persistence.criteria.Predicate;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.*;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.time.*;
import java.util.*;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ScanQueryService {
    private final AiRequestRepository requests;
    private final AccountRepository accounts;
    private final CurrentAccount current;
    private final EntityManager em;
    public record PageResult<T>(List<T> items, long total, int page, int size, int totalPages) {
        public static <T> PageResult<T> of(Page<T> page) { return new PageResult<>(page.getContent(), page.getTotalElements(), page.getNumber(), page.getSize(), page.getTotalPages()); }
    }
    public record ScanSummary(Integer id, Integer accountId, String fullName, String phone, Instant createdAt,
        String imageUrl, RequestStatus status, String errorMessage, int count, double confidenceAvg, List<String> materials, boolean requiresConfirmation,
        int componentCount, List<String> componentMaterials, String analysisMode) {}
    public static Pageable page(int page, int size) { return PageRequest.of(Math.max(0, page), Math.max(1, Math.min(50, size)), Sort.by(Sort.Direction.DESC, "id")); }
    public PageResult<ScanSummary> history(boolean admin, int page, int size, String q, String material, LocalDate from, LocalDate to) {
        Integer accountId = current.get().getId();
        var result = requests.findAll((root, query, cb) -> {
            List<Predicate> predicates = new ArrayList<>();
            if (!admin) predicates.add(cb.equal(root.get("account").get("id"), accountId));
            if (q != null && !q.isBlank()) {
                String term = "%" + q.toLowerCase(Locale.ROOT).trim() + "%";
                var owner = root.join("account", jakarta.persistence.criteria.JoinType.LEFT);
                predicates.add(cb.or(cb.like(cb.lower(owner.get("fullName")), term), cb.like(owner.get("phone"), term), cb.like(root.get("id").as(String.class), term)));
            }
            if (material != null && !material.isBlank()) {
                var sub = query.subquery(Integer.class);
                var d = sub.from(Detection.class);
                sub.select(d.get("id")).where(cb.equal(d.get("aiRequest"), root), cb.equal(d.get("label"), material));
                var parts = query.subquery(Integer.class);
                var c = parts.from(DetectionComponent.class);
                parts.select(c.get("id")).where(cb.equal(c.get("detection").get("aiRequest"), root), cb.equal(c.get("material"), material));
                predicates.add(cb.or(cb.exists(sub), cb.exists(parts)));
            }
            if (from != null) predicates.add(cb.greaterThanOrEqualTo(root.get("createdAt"), start(from)));
            if (to != null) predicates.add(cb.lessThan(root.get("createdAt"), start(to.plusDays(1))));
            return cb.and(predicates.toArray(Predicate[]::new));
        }, page(page, size));
        return PageResult.of(result.map(this::summary));
    }
    private ScanSummary summary(AiRequest r) {
        var a = r.getAccount();
        return new ScanSummary(r.getId(), a == null ? null : a.getId(), a == null ? "Tài khoản cũ" : a.getFullName(), a == null ? null : a.getPhone(),
            r.getCreatedAt(), r.getCloudinaryUrl(), ScanService.status(r), r.getErrorMessage(), r.getDetections().size(),
            r.getDetections().stream().filter(d -> d.getConfidence() != null).mapToDouble(Detection::getConfidence).average().orElse(0),
            r.getDetections().stream().map(Detection::getLabel).filter(Objects::nonNull).distinct().sorted().toList(),
            r.getDetections().stream().anyMatch(d -> "NEEDS_CONFIRM".equals(d.getStatus()) || d.getComponents().stream().anyMatch(c -> "NEEDS_CONFIRM".equals(c.getStatus()))),
            r.getDetections().stream().mapToInt(d -> d.getComponents().size()).sum(),
            r.getDetections().stream().flatMap(d -> d.getComponents().stream()).map(DetectionComponent::getMaterial).distinct().sorted().toList(),
            r.getAnalysisMode() == null ? "bottle" : r.getAnalysisMode());
    }
    public record UserView(Integer id, String fullName, String phone, String email, boolean active, LocalDateTime createdAt) {}
    public static UserView user(Account a) { return new UserView(a.getId(), a.getFullName(), a.getPhone(), a.getEmail(), Boolean.TRUE.equals(a.getIsActive()), a.getCreatedAt()); }
    public PageResult<UserView> users(int page, int size, String q) {
        return PageResult.of(accounts.findAll((root, query, cb) -> {
            var role = cb.equal(root.get("role"), AccountRole.USER);
            if (q == null || q.isBlank()) return role;
            String term = "%" + q.toLowerCase(Locale.ROOT).trim() + "%";
            return cb.and(role, cb.or(cb.like(cb.lower(root.get("fullName")), term), cb.like(root.get("phone"), term), cb.like(cb.lower(root.get("email")), term)));
        }, page(page, size)).map(ScanQueryService::user));
    }
    public record Bucket(String label, long count) {}
    public record Statistics(long totalScans, long totalUsers, long activeUsers, long failedScans, long completedScans,
        long totalObjects, double confidenceAvg, long needsConfirmation, List<Bucket> materials, List<Bucket> daily, LocalDate from, LocalDate to,
        long totalComponents, long componentsNeedingConfirmation, List<Bucket> componentMaterials) {}
    public Statistics statistics(LocalDate from, LocalDate to) {
        LocalDate today = LocalDate.now(ZoneId.of("Asia/Bangkok"));
        LocalDate end = to == null ? today : to;
        LocalDate begin = from == null ? end.minusDays(29) : from;
        if (begin.isAfter(end) || begin.isBefore(end.minusDays(365)))
            throw new com.example.hauiTrash.exception.BadRequestException("Khoảng thống kê cần từ 1 đến 366 ngày");
        Instant lo = start(begin), hi = start(end.plusDays(1));
        String scope = " r.createdAt >= :lo and r.createdAt < :hi";
        long total = count("select count(r) from AiRequest r where" + scope, lo, hi);
        long failed = count("select count(r) from AiRequest r where r.status = com.example.hauiTrash.entity.RequestStatus.ERROR and" + scope, lo, hi);
        long complete = count("select count(r) from AiRequest r where r.finishedAt is not null and (r.status is null or r.status = com.example.hauiTrash.entity.RequestStatus.DONE) and" + scope, lo, hi);
        var aggregate = em.createQuery("select count(d), avg(d.confidence) from Detection d join d.aiRequest r where" + scope, Object[].class)
            .setParameter("lo", lo).setParameter("hi", hi).getSingleResult();
        long confirm = count("select count(d) from Detection d join d.aiRequest r where d.status = 'NEEDS_CONFIRM' and" + scope, lo, hi);
        var materials = em.createQuery("select d.label, count(d) from Detection d join d.aiRequest r where" + scope + " group by d.label order by count(d) desc", Object[].class)
            .setParameter("lo", lo).setParameter("hi", hi).getResultList().stream().map(a -> new Bucket(String.valueOf(a[0]), ((Number)a[1]).longValue())).toList();
        long totalComponents = count("select count(c) from DetectionComponent c join c.detection d join d.aiRequest r where" + scope, lo, hi);
        long uncertainComponents = count("select count(c) from DetectionComponent c join c.detection d join d.aiRequest r where c.status = 'NEEDS_CONFIRM' and" + scope, lo, hi);
        var componentMaterials = em.createQuery("select c.material, count(c) from DetectionComponent c join c.detection d join d.aiRequest r where" + scope + " group by c.material order by count(c) desc", Object[].class)
            .setParameter("lo", lo).setParameter("hi", hi).getResultList().stream().map(a -> new Bucket(String.valueOf(a[0]), ((Number)a[1]).longValue())).toList();
        // Shift UTC instants to the same +07:00 calendar used by date filters and the frontend.
        var times = em.createQuery("select r.createdAt from AiRequest r where" + scope, Instant.class).setParameter("lo", lo).setParameter("hi", hi).getResultList();
        Map<String, Long> grouped = new HashMap<>();
        times.forEach(t -> grouped.merge(t.atZone(ZoneId.of("Asia/Bangkok")).toLocalDate().toString(), 1L, Long::sum));
        List<Bucket> daily = new ArrayList<>();
        for (LocalDate day = begin; !day.isAfter(end); day = day.plusDays(1)) daily.add(new Bucket(day.toString(), grouped.getOrDefault(day.toString(), 0L)));
        return new Statistics(total, accounts.count((r,q,c) -> c.equal(r.get("role"), AccountRole.USER)),
            accounts.count((r,q,c) -> c.and(c.equal(r.get("role"), AccountRole.USER), c.isTrue(r.get("isActive")))), failed, complete,
            ((Number)aggregate[0]).longValue(), aggregate[1] == null ? 0 : ((Number)aggregate[1]).doubleValue(), confirm, materials, daily, begin, end,
            totalComponents, uncertainComponents, componentMaterials);
    }
    private long count(String jpql, Instant lo, Instant hi) { return em.createQuery(jpql, Long.class).setParameter("lo", lo).setParameter("hi", hi).getSingleResult(); }
    private static Instant start(LocalDate date) { return date.atStartOfDay(ZoneId.of("Asia/Bangkok")).toInstant(); }
}
