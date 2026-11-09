# Job detector bộ phận đang chạy

Run: `AI_DATASET/bottle_components/05_models/research-detector-v2`.

Job CPU tối đa 40 epoch, YOLO11n, ảnh 416, batch 2, 4 thread. Sử dụng 402 crop train / 24 val / 49 test từ nhãn hình học SPIN đã công bố. Chỉ validation được dùng chọn checkpoint; test chạy riêng sau train. Dataset có các giới hạn đã ghi trong `04_prepared/public-detector-v1/source-acceptance.json`, chưa phải kiểm thử cuối cùng trên ảnh chai thật độc lập.

## Theo dõi

```powershell
Get-Content 'D:\thacsi\DOAN\HAUI-TRASH\AI_DATASET\bottle_components\05_models\research-detector-v2\status.json'
Get-Content 'D:\thacsi\DOAN\HAUI-TRASH\AI_DATASET\bottle_components\05_models\research-detector-v2.stdout.log' -Tail 15
```

Job chạy nền, tiếp tục chạy khi kết thúc lượt chat nếu máy vẫn hoạt động. Không tự thay cài đặt nguồn/sleep của Windows. Log stderr riêng có cùng tiền tố `.stderr.log`.

Các phase: `VALIDATING` → `TRAINING` → `EVALUATING` → `PROPOSING_COMPONENTS` → `READY_FOR_REVIEW`. `FAILED` ghi lỗi để xử lý; `STOPPED` là dừng có yêu cầu. `maxEpochs=40` là giới hạn, có thể kết thúc sớm theo patience=10. `epoch` là epoch hoàn thành gần nhất; `actualTorchThreads` ghi số thread thực.

Các điểm validation trong status là chỉ số detector trên nguồn nghiên cứu nhỏ, không phải độ chính xác vật liệu hoặc độ chính xác website.

## Đầu ra tự động

- Checkpoint: `research-detector-v2/training/detector/weights/best.pt` và `last.pt`.
- Báo cáo test detector: `research-detector-v2/evaluation/detector-test.json`.
- Khung bộ phận gợi ý: `02_annotations/user-component-proposals-research-detector-v2.jsonl`, kèm `.report.json`.
- Khi hoàn tất, `proposals.active.json` trỏ tới file mới cho công cụ gán nhãn. Annotation đã duyệt trong master được ưu tiên; file proposal cũ giữ nguyên để đối chiếu.

Các đề xuất vẫn có `annotationReviewed=false`, `partsExhaustive=false`; vật liệu mỗi bộ phận là `unknown`, `materialVerified=false`. Các ảnh/khung bị loại theo rà soát hoặc chính sách trùng không được chấp nhận làm nhãn train. Report ghi các ảnh bỏ qua/lỗi để rà soát; không giả định mọi ảnh đều phân tích thành công.

Job không ghi vào `release.json`, không thay checkpoint chai cũ, không bật model mới trên website. Model vật liệu bộ phận cần crop đã gán nhãn và vật liệu được kiểm chứng; chưa được train trong job này.

## Dữ liệu đã chuẩn bị

- `02_annotations/exact-dedup-policy.json`: 136 bản dư từ 129 nhóm file trùng; giữ một bản ưu tiên test rồi val rồi train. Chỉ loại khỏi đầu vào train bằng metadata, giữ nguyên ảnh và CSV.
- `02_annotations/curation-v1/queue.jsonl`: hàng đợi 1.280 ảnh ứng viên; `plan.json` ghi checksum nguồn và CSV.
- `similarity-review.json`: 83 cặp ảnh giống nhau cần kiểm tra, trong đó 41 cặp khác split. Đây là gợi ý, không tự kết luận cùng sản phẩm hoặc tự gộp nhóm.
- `scope-reviews.jsonl`: đợt rà soát trực quan 30 ảnh, gồm 16 có chai, 7 không có chai, 7 chưa rõ phạm vi. Chỉ xác nhận hình dạng/phạm vi; không xác minh vật liệu. Có 7 khung giả bị đánh dấu loại.
- Quyết định scope/dedup có SHA256; nếu ảnh thay đổi, quyết định cũ không được áp dụng tiếp.

Vẫn cần rà soát phần còn lại của hàng đợi, điều chỉnh khung cha, bổ sung các bộ phận nhìn thấy và kiểm tra vật liệu. Các ảnh gợi ý chưa được tự đưa vào master hoặc export.

## Chạy một job mới khi cần

```powershell
python -u -X utf8 -m trashsmart.components research-cycle --data 'D:\thacsi\DOAN\HAUI-TRASH\AI_DATASET\bottle_components' --output 'D:\thacsi\DOAN\HAUI-TRASH\AI_DATASET\bottle_components\05_models\research-detector-v3' --weights '.\yolo11n.pt' --epochs 40 --imgsz 416 --batch 2 --threads 4
```

Không khởi động thêm khi job hiện tại còn chạy. Mỗi job dùng output mới. Có thể dùng `--weights` trỏ tới checkpoint ứng viên trước để khởi tạo job mới; đây không phải resume chính xác optimizer. Research runner không nhận `--resume`.

Để yêu cầu dừng sau epoch hiện tại, tạo file `stop.requested` trong thư mục run. Job giữ checkpoint và không chạy các bước hậu xử lý tiếp theo sau khi dừng. Nếu cần xử lý lỗi hoặc khôi phục sau khi mất điện, giữ nguyên thư mục run/log/checkpoint để kiểm tra trước khi chạy job mới.
