package com.example.hauiTrash.service;

import com.example.hauiTrash.dto.*;
import com.example.hauiTrash.entity.*;
import com.example.hauiTrash.repository.*;
import com.example.hauiTrash.security.CurrentAccount;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.data.domain.*;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.*;
import static com.example.hauiTrash.dto.ComponentLearningDTO.*;
import com.example.hauiTrash.dto.ComponentLearningDTO.Queue;

@Service @RequiredArgsConstructor
public class ComponentLearningService {
    private final ComponentLearningCaseRepository cases;
    private final AiRequestRepository requests;
    private final CurrentAccount current;

    @Transactional
    public void attachCases(AiResponseDetailsDTO snapshot,DetailedAnalysisDTO result) {
        var scan=requests.findForUpdate(snapshot.getId()).orElseThrow(()->error(HttpStatus.NOT_FOUND,"Không tìm thấy lượt quét."));
        current.checkOwner(scan);
        if(!Objects.equals(snapshot.getCloudinaryUrl(),scan.getCloudinaryUrl()))throw error(HttpStatus.CONFLICT,"Ảnh của lượt quét đã thay đổi. Hãy tải lại kết quả.");
        var parents=new HashMap<Integer,Detection>();for(var d:scan.getDetections())parents.put(d.getId(),d);
        for(var parent:result.getParents())for(var component:parent.getComponents()){
            var d=parents.get(parent.getDetectionId());
            if(d==null||component.getX1()<d.getX1()||component.getY1()<d.getY1()||component.getX2()>d.getX2()||component.getY2()>d.getY2())
                throw error(HttpStatus.CONFLICT,"Vị trí chai đã thay đổi. Hãy tải lại kết quả.");
            String key=hash(String.join("|",scan.getId().toString(),d.getId().toString(),result.getModelVersion(),
                scan.getCloudinaryUrl(),component.getPartType(),component.getMaterial(),
                component.getX1()+","+component.getY1()+","+component.getX2()+","+component.getY2()));
            var item=cases.findById(key).orElseGet(()->{
                boolean unknown="unknown".equals(component.getMaterial());
                return cases.saveAndFlush(ComponentLearningCase.builder().id(key).scan(scan).detectionId(d.getId())
                    .modelVersion(result.getModelVersion()).imageUrl(scan.getCloudinaryUrl())
                    .imageWidth(result.getImageWidth()).imageHeight(result.getImageHeight()).partType(component.getPartType())
                    .predictedMaterial(component.getMaterial()).detectionConfidence(component.getDetectionConfidence())
                    .materialConfidence(component.getMaterialConfidence()).x1(component.getX1()).y1(component.getY1()).x2(component.getX2()).y2(component.getY2())
                    .queryRecommended(unknown||component.getMaterialConfidence()<.8f||component.getDetectionConfidence()<.6f)
                    .priority(unknown?1d:1d-Math.min(component.getMaterialConfidence(),component.getDetectionConfidence()))
                    .feedbackState("OPEN").createdAt(Instant.now()).build());
            });
            component.setLearningCaseId(item.getId());component.setQueryRecommended(item.getQueryRecommended());
            component.setQueryPriority(item.getPriority());component.setFeedbackState(item.getFeedbackState());
            component.setHumanMaterial(item.getHumanMaterial());component.setFeedbackRevision(item.getRevision());
        }
    }

    @Transactional(readOnly=true)
    public List<CaseView> forScan(Integer scanId){
        var scan=requests.findById(scanId).orElseThrow(()->error(HttpStatus.NOT_FOUND,"Không tìm thấy lượt quét."));
        current.checkOwner(scan);return cases.findByScanIdOrderByPriorityDesc(scanId).stream().map(ComponentLearningService::view).toList();
    }

    @Transactional
    public CaseView feedback(Integer scanId,String caseId,Feedback body){
        var item=cases.findLocked(caseId).orElseThrow(()->error(HttpStatus.NOT_FOUND,"Không tìm thấy bộ phận."));
        var actor=current.get();
        if(!item.getScan().getId().equals(scanId)||item.getScan().getAccount()==null||!item.getScan().getAccount().getId().equals(actor.getId()))
            throw error(HttpStatus.FORBIDDEN,"Bạn chỉ được xác nhận bộ phận trong lượt quét của mình.");
        revision(item,body.revision());
        if(!"OPEN".equals(item.getFeedbackState()))throw error(HttpStatus.CONFLICT,"Bộ phận này đã được gửi xác nhận. Không gửi trùng.");
        if(!"unknown".equals(body.material())&&"UNSURE".equals(body.verificationBasis()))throw error(HttpStatus.BAD_REQUEST,"Chọn cách kiểm chứng, hoặc chọn Không chắc chắn.");
        item.setHumanMaterial(body.material());item.setVerificationBasis(body.verificationBasis());item.setRegionCorrect(body.regionCorrect());
        item.setTrainingConsent(body.trainingConsent());item.setHumanNote(clean(body.note()));item.setSubmittedBy(actor);
        item.setSubmittedAt(Instant.now());item.setFeedbackState("PENDING");cases.saveAndFlush(item);return view(item);
    }

    @Transactional(readOnly=true)
    public Queue queue(String state,int page,int size){
        admin();if(!Set.of("OPEN","PENDING","APPROVED","REJECTED").contains(state))throw error(HttpStatus.BAD_REQUEST,"Trạng thái không hợp lệ.");
        var rows=cases.findByFeedbackState(state,page(page,size));
        return new Queue(rows.getContent().stream().map(ComponentLearningService::view).toList(),rows.getTotalElements(),rows.getNumber(),rows.getTotalPages(),
            cases.countByFeedbackState("PENDING"),cases.countByFeedbackState("APPROVED"),cases.countByFeedbackState("REJECTED"));
    }

    @Transactional
    public CaseView review(String caseId,Review body){
        var actor=admin();var item=cases.findLocked(caseId).orElseThrow(()->error(HttpStatus.NOT_FOUND,"Không tìm thấy xác nhận."));
        revision(item,body.revision());
        if(!"PENDING".equals(item.getFeedbackState()))throw error(HttpStatus.CONFLICT,"Chỉ duyệt xác nhận đang chờ xử lý.");
        if(item.getSubmittedBy()!=null&&item.getSubmittedBy().getId().equals(actor.getId()))throw error(HttpStatus.CONFLICT,"Cần người quản trị khác duyệt xác nhận của bạn.");
        if("APPROVE".equals(body.decision())&&body.verificationBasis()!=null){
            if(!Boolean.TRUE.equals(body.confirmedCorrect())||body.note()==null||body.note().isBlank())
                throw error(HttpStatus.BAD_REQUEST,"Chọn xác nhận đúng và ghi căn cứ kiểm chứng của admin.");
            item.setAdminVerificationBasis(body.verificationBasis());
        }
        if("APPROVE".equals(body.decision())&&!eligible(item))throw error(HttpStatus.BAD_REQUEST,
            "Cần căn cứ của người dùng hoặc xác nhận độc lập của admin, vùng đúng và người dùng đồng ý cho học.");
        if("REJECT".equals(body.decision())&&(body.note()==null||body.note().isBlank()))throw error(HttpStatus.BAD_REQUEST,"Ghi lý do cần loại khỏi dữ liệu học.");
        item.setFeedbackState("APPROVE".equals(body.decision())?"APPROVED":"REJECTED");item.setReviewedBy(actor);
        item.setReviewedAt(Instant.now());item.setReviewNote(clean(body.note()));cases.saveAndFlush(item);return view(item);
    }

    @Transactional(readOnly=true)
    public Map<String,Object> export(int page,int size){
        admin();var rows=cases.findByFeedbackStateAndTrainingConsentTrueAndRegionCorrectTrue("APPROVED",page(page,size));
        List<Map<String,Object>> records=new ArrayList<>();
        for(var c:rows)if(eligible(c)){
            var row=new LinkedHashMap<String,Object>();row.put("schemaVersion",1);row.put("caseId",c.getId());
            row.put("imageUrl",c.getImageUrl());row.put("imageWidth",c.getImageWidth());row.put("imageHeight",c.getImageHeight());
            row.put("groupId","scan-"+c.getScan().getId());row.put("modelVersion",c.getModelVersion());row.put("partType",c.getPartType());
            row.put("bbox",List.of(c.getX1(),c.getY1(),c.getX2(),c.getY2()));row.put("material",c.getHumanMaterial());
            row.put("verificationBasis",effectiveBasis(c));row.put("userVerificationBasis",c.getVerificationBasis());
            row.put("adminVerificationBasis",c.getAdminVerificationBasis());row.put("verificationSource",c.getAdminVerificationBasis()==null?"USER":"ADMIN");
            row.put("adminReviewed",true);row.put("trainingConsent",true);row.put("regionCorrect",true);
            row.put("split","train");records.add(row);
        }
        var result=new LinkedHashMap<String,Object>();result.put("schemaVersion",1);result.put("records",records);
        result.put("nextPage",rows.hasNext()?page+1:null);result.put("total",rows.getTotalElements());
        result.put("notice","Nhãn đã duyệt để tạo dữ liệu học; chưa cập nhật model đang chạy.");return result;
    }

    private Account admin(){var a=current.get();if(a.getRole()!=AccountRole.ADMIN)throw error(HttpStatus.FORBIDDEN,"Chỉ quản trị viên được duyệt dữ liệu học.");return a;}
    private static String effectiveBasis(ComponentLearningCase c){return c.getAdminVerificationBasis()==null?c.getVerificationBasis():
        "VISUAL_REVIEW".equals(c.getAdminVerificationBasis())?"ADMIN_VISUAL_REVIEW":c.getAdminVerificationBasis();}
    private static boolean eligible(ComponentLearningCase c){return Set.of("glass","metal","paper","plastic").contains(Objects.toString(c.getHumanMaterial(),""))
        &&Set.of("PHYSICAL_CHECK","PACKAGING_MARK","ADMIN_VISUAL_REVIEW").contains(Objects.toString(effectiveBasis(c),""))
        &&Boolean.TRUE.equals(c.getRegionCorrect())&&Boolean.TRUE.equals(c.getTrainingConsent());}
    private static Pageable page(int p,int s){if(p<0||s<1||s>100)throw error(HttpStatus.BAD_REQUEST,"Phân trang không hợp lệ.");return PageRequest.of(p,s,Sort.by(Sort.Order.desc("priority"),Sort.Order.asc("createdAt"),Sort.Order.asc("id")));}
    private static void revision(ComponentLearningCase c,Long expected){if(!Objects.equals(c.getRevision(),expected))throw error(HttpStatus.CONFLICT,"Dữ liệu đã thay đổi. Hãy tải lại trước khi xác nhận.");}
    private static String clean(String value){return value==null?null:value.strip();}
    private static String hash(String value){try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));}catch(Exception error){throw new IllegalStateException(error);}}
    private static ResponseStatusException error(HttpStatus status,String message){return new ResponseStatusException(status,message);}
    private static CaseView view(ComponentLearningCase c){return new CaseView(c.getId(),c.getScan().getId(),c.getDetectionId(),c.getModelVersion(),c.getImageUrl(),c.getImageWidth(),c.getImageHeight(),
        c.getPartType(),c.getPredictedMaterial(),c.getMaterialConfidence(),c.getDetectionConfidence(),c.getX1(),c.getY1(),c.getX2(),c.getY2(),c.getPriority(),c.getQueryRecommended(),
        c.getFeedbackState(),c.getHumanMaterial(),c.getVerificationBasis(),c.getRegionCorrect(),c.getTrainingConsent(),c.getHumanNote(),c.getSubmittedAt(),c.getReviewNote(),c.getReviewedAt(),c.getRevision(),c.getAdminVerificationBasis());}
}
