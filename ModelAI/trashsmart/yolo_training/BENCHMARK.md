# So sánh YOLO11n và YOLOv8n

Chạy các lệnh dưới từ thư mục `VisionSortAI/ModelAI`. Thí nghiệm đánh giá phát
hiện một lớp `item` trên cùng dữ liệu của dự án.

- YOLO11n đạt mAP50–95 **52,65%** và F1 **78,84%** tại confidence 0,25.
- YOLOv8n đạt mAP50–95 **52,58%** và F1 **82,24%** tại confidence 0,25.

Chênh lệch mAP50–95 là 0,073 điểm phần trăm theo hướng YOLO11n. F1 tại ngưỡng
chung cao hơn ở YOLOv8n. Các số liệu thuộc đợt chạy 20 epoch, ảnh 416 pixel và seed 42.

## Python trên máy hiện tại

Dùng PowerShell.

```powershell
$python = 'C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.14-64\python.exe'
```

Máy khác có thể dùng `$python = 'python'` sau khi cài đúng thư viện của ModelAI.
Checkpoint pretrained `yolo11n.pt` và `yolov8n.pt` phải nằm ở thư mục ModelAI.
Khi cần tải checkpoint chính thức, dùng Ultralytics.

```powershell
& $python -c "from ultralytics import YOLO; YOLO('yolo11n.pt'); YOLO('yolov8n.pt')"
```

## Thí nghiệm đã cấu hình trên CPU

Giao thức gồm 20 epoch, kích thước ảnh 416, batch 8, 4 thread CPU, seed 42,
AdamW với learning rate ban đầu 0.001 và cùng augmentation.
Hai lượt dùng cache ảnh trong RAM. Phiên bản thư viện và phần cứng ảnh hưởng khả năng tái lập.
Hai mô hình bắt đầu từ COCO pretrained 80 lớp. Chọn `best.pt` bằng mAP50-95
validation. Đánh giá cuối trên cùng 182 ảnh test, 261 chai có nhãn.

Thư mục `outputs/yolo11-vs-yolov8` giữ bản dữ liệu, giao thức, checkpoint ban
đầu và kết quả. Hash của bản dữ liệu được kiểm tra ở các bước train và evaluate.
Tập test đã được dùng trong các đánh giá cũ của dự án.
Xem `data_audit.json` về ảnh gần giống giữa train và validation.

## Test riêng từng model trên cùng một ảnh

Bỏ tham số `--image` để mở hộp thoại chọn ảnh trên máy. `--show` tự mở ảnh kết
quả sau khi nhận diện. Hai lệnh dưới chạy độc lập, mỗi lần chạy bạn tự chọn ảnh.

```powershell
& 'C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.14-64\python.exe' -m trashsmart.yolo_training.predict_compare --model yolo11 --conf 0.25 --iou 0.7 --output outputs/test-anh-yolo11 --show

& 'C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.14-64\python.exe' -m trashsmart.yolo_training.predict_compare --model yolov8 --conf 0.25 --iou 0.7 --output outputs/test-anh-yolov8 --show
```

Để dùng một ảnh cho nhiều lệnh, bạn có thể lấy đường dẫn qua hộp thoại rồi gán
cho biến `$image`.

```powershell
$image = & $python -c "from trashsmart.yolo_training.predict_compare import select_image; image = select_image(); print(image or '')"
```

Các lệnh có `--image $image` dưới đây dùng ảnh đã chọn. Nếu bấm hủy, chạy lại
lệnh chọn ảnh trước khi tiếp tục.

Mỗi lệnh lưu ảnh có khung phát hiện và `predictions.json` chứa số khung,
tọa độ, confidence và thời gian suy luận. Script mặc định lấy kích
thước ảnh từ `protocol.json`, nên hai lệnh cùng dùng 416 px của thí nghiệm này.
Lần chạy lặp tự tăng số ở tên thư mục kết quả.

Chạy cả hai trong một lệnh để có thêm ảnh đặt cạnh nhau.

```powershell
& $python -m trashsmart.yolo_training.predict_compare --model both --image $image --conf 0.25 --iou 0.7 --output outputs/test-anh-ca-hai
```

Đối chiếu thêm bản sao checkpoint YOLO11 của API tại thời điểm bắt đầu thí nghiệm.

```powershell
& $python -m trashsmart.yolo_training.predict_compare --model existing --image $image --conf 0.25 --iou 0.7 --output outputs/test-anh-yolo11-hien-tai
```

Chọn checkpoint cụ thể bằng `--weights`.

```powershell
& $python -m trashsmart.yolo_training.predict_compare --model yolo11 --weights trashsmart/models/best_new.pt --imgsz 640 --image $image --output outputs/test-checkpoint-rieng
```

Thời gian là median của 10 lần `model.predict` sau 2 lần làm nóng, gồm tiền
xử lý, suy luận và NMS trên mảng ảnh đã đọc vào RAM. Confidence mô tả từng dự
đoán. mAP và P/R/F1 được tính bằng cách đối chiếu dự đoán với nhãn chuẩn.

## Tạo và train thí nghiệm mới

Ví dụ dưới đây cấu hình 100 epoch ở 640 px với tên thư mục cho đợt mới.
Tham số `--epochs 20 --imgsz 416` lặp lại ngân sách đã chạy trong đợt hiện tại.
Thiết bị CUDA được chọn bằng `--device 0` khi môi trường có PyTorch CUDA và GPU phù hợp.

```powershell
& $python -m trashsmart.yolo_training.benchmark --source 'D:\thacsi\DOAN\HAUI-TRASH\data\data-yolo' --output outputs/yolo11-vs-yolov8-100ep --epochs 100 --imgsz 640 --batch 8 --threads 4 --seed 42 --device cpu --stage prepare
```

Train riêng YOLO11n.

```powershell
& $python -m trashsmart.yolo_training.benchmark --output outputs/yolo11-vs-yolov8-100ep --stage train --model yolo11
```

Train riêng YOLOv8n.

```powershell
& $python -m trashsmart.yolo_training.benchmark --output outputs/yolo11-vs-yolov8-100ep --stage train --model yolov8
```

Lệnh sau train lần lượt cả hai.

```powershell
& $python -m trashsmart.yolo_training.benchmark --output outputs/yolo11-vs-yolov8-100ep --stage train
```

Các bước train/evaluate đọc cấu hình đã ghi trong `protocol.json`.
Huấn luyện được thực hiện lần lượt trong cùng thư mục thí nghiệm.

## Đánh giá trên cùng tập test và đọc kết quả

Đánh giá sau khi cả hai đã train xong.

```powershell
& $python -m trashsmart.yolo_training.benchmark --output outputs/yolo11-vs-yolov8-100ep --stage evaluate
```

Khi thử ảnh với thí nghiệm mới, truyền `--experiment` để chọn đúng hai checkpoint.

```powershell
& $python -m trashsmart.yolo_training.predict_compare --experiment outputs/yolo11-vs-yolov8-100ep --model both --image $image --output outputs/test-anh-100ep
```

- `protocol.json`: phiên bản thư viện, cấu hình, seed và hash checkpoint đầu vào.
- `data_audit.json`: số ảnh/đối tượng, hash dữ liệu, kiểm tra trùng và ảnh gần giống.
- `yolo11n/weights/best.pt`, `yolov8n/weights/best.pt`: hai model mới.
- `yolo11n/results.csv`, `yolov8n/results.csv`: chỉ số theo epoch.
- `comparison.json`, `comparison.csv`: kết quả test của hai model và model API cũ.
- `training_comparison.png`: đường mAP50-95 validation và loss train.
- `evaluation/`: PR curve, confusion matrix và các ảnh do Ultralytics xuất.
- `progress.json`, `training.log`: tiến độ và nhật ký của lần chạy trên máy hiện tại.

Precision/Recall/F1 tại confidence cố định 0.25 được đo bằng đối sánh lại IoU
0.5 sau khi lọc confidence. Cột `precision_max_f1`/`recall_max_f1` là điểm do
Ultralytics chọn trên đường cong. AP được
tính với confidence thấp 0.001 và IoU đánh giá 0.50 đến 0.95. `iou=0.7` là
ngưỡng NMS.

Kết luận chính so sánh mAP50-95 test của hai lượt train mới. Checkpoint API cũ
có lịch sử fine-tune riêng và được đánh giá theo cấu hình suy luận chung.
Phạm vi kết quả gồm một seed và ngân sách 20 epoch đã chạy.
Tốc độ validation batch đo suy luận theo batch trên tập test.

Các tệp CSV/JSON lưu Precision, Recall, F1 và mAP theo tỷ lệ 0–1. Bảng trong
đồ án nhân 100 để trình bày theo phần trăm. Nếu quá trình chạy bị gián đoạn,
cột thời gian train được ghi trạng thái gián đoạn. `execution_interruptions.json`
lưu các sự kiện thời gian của đợt chạy.

## Đợt so sánh trên ba bộ dữ liệu

Thư mục `outputs/yolo-three-datasets-20261115` chứa giao thức mở rộng trong
`study_plan.json`. Mỗi bộ dữ liệu có một cặp YOLO11n và YOLOv8n được train riêng
từ COCO pretrained với cùng 30 epoch, ảnh 640 px, batch 8, CPU 4 thread và seed 42.
Recipe `accuracy` dùng AdamW, `lr0=0.0005`, `cls=1.0`, `mosaic=0.5`,
`close_mosaic=10`, `scale=0.3`, `hsv_s=0.4`, `hsv_v=0.3`.
Checkpoint được chọn theo mAP50–95 validation. Cấu hình là một thử nghiệm tối ưu
có ngân sách xác định. Mức cải thiện được xác nhận bằng kết quả đo của từng bộ.

- HAUI dùng bản dữ liệu đã khóa của dự án, với phạm vi nhãn đối tượng hiện có.
- TACO dùng bản lưu trữ chính thức v0.1 gồm 715 ảnh và 2.152 annotation. Nhãn
  rác gốc được gộp thành `item`. [Nguồn TACO](https://zenodo.org/records/3354286)
- UAVVaste gồm 772 ảnh và 3.718 annotation rác trên ảnh chụp từ trên cao.
  [Nguồn UAVVaste](https://zenodo.org/records/8214061)

Hai gói công khai được kiểm tra MD5 theo kho phát hành. Ảnh được xoay theo EXIF
cho khớp kích thước nhãn COCO và resize giữ toàn khung, cạnh dài tối đa 1.280 px.
TACO được chia theo nhóm batch, UAVVaste theo tiền tố phiên chụp. Tỷ lệ mục tiêu
train/validation/test là 70/15/15 với seed 42, giữ cả nhóm trong một split.
Số ảnh thực tế và kiểm tra trùng nằm trong `datasets/<tên bộ>/data_audit.json`.
Nguồn ảnh, annotation và các nhóm chia tập được lưu trong `source.json`.
Khung YOLO được tạo bằng hình chữ nhật bao quanh polygon segmentation gốc.
Trong gói TACO v0.2, 2.150/2.152 trường `bbox` có tọa độ y tính từ đáy ảnh,
trong khi polygon dùng hệ tọa độ ảnh từ trên xuống. Quy tắc polygon sửa sự lệch
hệ tọa độ đó trước huấn luyện. `source.json` lưu cả `source_bbox` và
`polygon_envelope` để đối chiếu. Quy tắc được áp dụng chung cho cả hai mô hình.

Để tải và chuẩn bị lại dữ liệu công khai, chạy lần lượt các lệnh sau từ `ModelAI`.
Mỗi bộ dữ liệu được chuẩn bị bằng một tiến trình tại một thời điểm.

```powershell
& $python -m trashsmart.yolo_training.public_datasets --dataset taco
& $python -m trashsmart.yolo_training.public_datasets --dataset uavvaste
```

Sau khi các lượt chạy kết thúc, bảng đối chiếu ba bộ được ghi tại
`comparison_three_datasets.csv` và `comparison_three_datasets.json` trong thư mục
đợt mở rộng. Báo cáo ghi P/R/F1 tại confidence 0,25, mAP50, mAP50–95, TP/FP/FN,
số tham số, dung lượng checkpoint và thời gian suy luận. Chênh lệch được tính
cho từng chỉ số, gồm cả trường hợp YOLO11n thấp hơn YOLOv8n.

Chọn cặp mô hình của một bộ dữ liệu bằng `--experiment`. Ví dụ sau mở hộp thoại
chọn ảnh rồi chạy riêng YOLO11n hoặc YOLOv8n của bộ HAUI sau khi train hoàn tất.

```powershell
& 'C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.14-64\python.exe' -m trashsmart.yolo_training.predict_compare --experiment outputs/yolo-three-datasets-20261115/haui --model yolo11 --output outputs/test-haui-moi-yolo11 --show
& 'C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.14-64\python.exe' -m trashsmart.yolo_training.predict_compare --experiment outputs/yolo-three-datasets-20261115/haui --model yolov8 --output outputs/test-haui-moi-yolov8 --show
```

Thay `haui` bằng `taco` hoặc `uavvaste` để chọn cặp checkpoint tương ứng.
Phạm vi đối tượng được mô tả riêng cho từng bộ trong `study_plan.json`.

### Kết quả đợt mở rộng đã hoàn thành

Cả sáu lượt đã chạy đủ 30 epoch và được đánh giá trên tập test tương ứng.
YOLO11n đạt mAP50–95 53,59% trên HAUI, 32,50% trên TACO và 39,90% trên
UAVVaste. YOLOv8n lần lượt đạt 54,06%, 34,23% và 38,45%. F1 tại confidence
0,25 của YOLO11n là 83,49%, 48,76%, 70,06%; YOLOv8n là 83,46%, 53,25%,
67,69%. Các giá trị đầy đủ gồm cả Precision, Recall, TP/FP/FN và chênh lệch
nằm trong JSON/CSV của đợt mở rộng. Kết quả chưa cho thấy YOLO11n vượt trội
ở tất cả tiêu chí hoặc trên mọi bộ dữ liệu.

Đây là phép thử một seed với ngân sách đã định, không chứng minh cấu hình tối ưu
toàn cục. HAUI có lịch sử dùng test trước đây. Lượt YOLOv8n trên HAUI bị dừng
sau epoch 18 và được resume bằng optimizer, cấu hình gốc; hồ sơ lưu checkpoint
trước khôi phục và giới hạn về tính liên tục của chuỗi số ngẫu nhiên.
`haui/execution_interruptions.json` ghi sự kiện này. TACO và UAVVaste chạy liên tục.

Mỗi bộ là một bài toán phát hiện một lớp theo phạm vi nhãn riêng của nguồn,
không phải độ chính xác phân loại vật liệu. Không gộp các mAP thành một số
accuracy chung. Tốc độ validation theo batch và tốc độ ảnh đơn trong
`sample_prediction/predictions.json` có phạm vi đo khác nhau, chịu ảnh hưởng
tải CPU và điều kiện chạy.

Hai bản Word cập nhật nằm trong `outputs/yolo-three-datasets-20261115/documents`.
Ảnh thử cùng đầu vào của ba cặp mô hình nằm trong `<bộ dữ liệu>/sample_prediction`.
Để tự chọn ảnh và xem kết quả từng bộ, chạy hai lệnh độc lập ở trên; thay `haui`
bằng `taco` hoặc `uavvaste` nếu muốn dùng cặp trọng số của bộ đó.
