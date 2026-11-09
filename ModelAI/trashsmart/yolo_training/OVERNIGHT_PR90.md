# Train qua đêm: Precision và Recall cùng đạt 90%

Mục tiêu bắt buộc là **Precision >= 0,90 và Recall >= 0,90**. Cả hai giá trị
chuẩn max-F1 và cả hai giá trị tại cùng ngưỡng chạy API phải đạt mục tiêu.
mAP50 cũng phải >= 0,90. Không có phương án hạ Precision xuống 75–80% để báo
Recall 90% là đạt yêu cầu.

## Lượt CPU hiện tại

Model YOLO11s pretrained chính thức có khoảng 9,46 triệu tham số. Dataset dùng
`outputs/yolo-detection-clean/data.yaml`, đã sửa các file nhãn trộn polygon/bbox.
Ảnh, split và dữ liệu gốc được giữ nguyên. Quy trình chạy tuần tự với 4 luồng CPU:

1. Train head/neck, đóng băng backbone, tối đa 8 epoch.
2. Mở toàn bộ backbone, fine-tune với learning rate nhỏ hơn.
3. Polish với learning rate thấp và tắt Mosaic.

Ngân sách mặc định khoảng 8 giờ; đọc model và đánh giá cuối có thể thêm thời gian.
Checkpoint tốt nhất được chọn theo `min(Precision, Recall)`, sau đó F1 và mAP50.
Early stopping theo Precision/Recall, không theo riêng loss hay mAP50–95.
Các checkpoint và optimizer snapshot được lưu mỗi epoch.

```powershell
python -u -m trashsmart.yolo_training.overnight_pr90 --pretrained outputs/yolo-pr90-pretrained/yolo11s.pt --data outputs/yolo-detection-clean/data.yaml --run-dir outputs/yolo-pr90-overnight-20261027 --hours 8 --threads 4 --batch 4
```

Không chạy lại lệnh này nếu lượt có cùng thư mục còn chạy. Một lượt mới cần tên
thư mục mới. Lượt train đã được khởi chạy nền sẽ tiếp tục khi đóng chat.

## Theo dõi

### Tiếp tục từ checkpoint đã fine-tune

Thêm `--continuation` để bỏ bước train head, dùng learning rate 0.00005 và
Mosaic 0.15, sau đó polish không Mosaic. Checkpoint đầu vào được đánh giá trên
validation và giữ làm mốc; kết quả kém hơn không thay thế checkpoint này.
Đây là lượt fine-tune với optimizer mới, không khôi phục optimizer cũ.

```powershell
python -u -m trashsmart.yolo_training.overnight_pr90 --continuation --pretrained outputs/yolo-pr90-overnight-20261027/candidate.pt --data outputs/yolo-detection-clean/data.yaml --run-dir outputs/yolo-pr90-continue-20261028 --hours 8 --threads 4 --batch 4
```

Phân tích ảnh lỗi chỉ trên validation (không sửa nhãn tự động):

```powershell
python -m trashsmart.yolo_training.audit_errors --model outputs/yolo-pr90-overnight-20261027/candidate.pt --data outputs/yolo-detection-clean/data.yaml --output outputs/yolo-pr90-errors-20261028.json
```

Báo cáo chẩn đoán dùng ghép box theo confidence, có thể khác cách ghép của
Ultralytics. Chỉ số native trong báo cáo đánh giá vẫn là nguồn chính thức.
Nhóm `background_or_unlabeled` cần kiểm tra ảnh thủ công để xác định có thiếu nhãn.

```powershell
Get-Content outputs/yolo-pr90-overnight-20261027/progress.json -Raw
Get-Content outputs/yolo-pr90-overnight-20261027/head.log -Tail 10
```

Sau head, log tương ứng là `finetune.log` và `polish.log`. `progress.json` ghi PID,
giai đoạn, epoch, Precision/Recall validation và thời điểm cập nhật. Từng giai đoạn
có `best_precision_recall.pt`, `resume_last.pt` và `selection.json`.

Các giai đoạn bắt đầu optimizer mới. `resume_last.pt` giữ checkpoint đầy đủ;
để tiếp tục học từ trọng số sau gián đoạn có thể dùng `train_accuracy --model ...`
với một `--run-dir` mới; lệnh này không khôi phục trạng thái optimizer tự động.

## Điều kiện cập nhật API

Chọn checkpoint và confidence chỉ trên validation. Test chỉ được đánh giá một lần
với cấu hình cuối. Ảnh và nhãn được fingerprint; nếu chúng thay đổi giữa lượt train,
quy trình hủy cập nhật. Đây là kiểm tra nội dung chính xác, không phát hiện mọi ảnh
gần giống nhau hoặc cùng một vật thể trong nhiều phiên chụp.

- `complete_target_met`: các điều kiện Precision/Recall/mAP50 đạt trên validation
  và test; xem `publication.status` để biết model đã được áp dụng hay chưa.
- `complete_target_not_met`: chưa đạt; model API cũ được giữ nguyên.
- `failed`: xem `error` và log giai đoạn; các checkpoint trước đó vẫn còn.

Chỉ khi các điều kiện đồng thời đạt, quy trình mới backup và thay
`trashsmart/models/best_new.pt`, cập nhật các biến YOLO trong `.env`. Các giá trị
cấu hình khác được giữ nguyên. Nếu model đang dùng đã bị thay đổi trong lúc train,
quy trình không ghi đè. Không triển khai lên server/container bên ngoài.

Sau khi model mới được áp dụng, khởi động lại API để nạp trọng số mới. Windows
được yêu cầu giữ hệ thống thức trong lúc job chạy; màn hình vẫn có thể tắt/khóa.
Giữ máy cắm sạc và không tắt máy trong thời gian huấn luyện.
