# Thực nghiệm YOLO11n Original và Improved

Đóng góp cần kiểm chứng là tích hợp attention CBAM và thay CIoU bằng EIoU cho
bài toán phát hiện rác của dự án. Hai kỹ thuật có nguồn công bố; phần việc của
đồ án là thiết kế vị trí tích hợp, triển khai, kiểm chứng bằng ablation và đánh
giá trên ba bộ dữ liệu. Đồ án ghi rõ đây là ứng dụng và đánh giá các kỹ thuật
đã có, cùng các giới hạn thực nghiệm.

Bản thảo phương pháp có thể đọc trước khi train xong:
[Phương pháp và sơ đồ Original/Improved](../../docs/YOLO11n_ORIGINAL_IMPROVED_METHODS.md).
Nguồn trích dẫn có trong `ModelAI/docs/YOLO11n_REFERENCES.bib`.

## Định nghĩa đối chứng

- Original: kiến trúc YOLO11n nguyên bản, CIoU và DFL nguyên bản, được train
  trên tập rác tương ứng từ trọng số COCO pretrained.
- CBAM: thêm CBAM tại ba đầu ra neck P3/P4/P5, giữ CIoU.
- EIoU: thay thành phần CIoU của box regression bằng EIoU, giữ kiến trúc gốc.
- Improved: kết hợp CBAM và EIoU; đây là tên cấu hình ứng viên đã định trước.
  Kết quả có thể tăng hoặc giảm và đều được báo cáo.

Transfer learning áp dụng cho cả bốn hàng. Recipe huấn luyện chung được khóa
để tách tác động của hai yếu tố CBAM và EIoU. Original ở đây có nghĩa kiến trúc
và loss gốc; các siêu tham số chung là recipe đã công bố, không phải lời khẳng
định đang dùng toàn bộ mặc định `optimizer=auto` của Ultralytics.

Đợt mới chạy 12 lượt từ đầu: 4 cấu hình × 3 bộ HAUI, TACO, UAVVaste. Mỗi lượt
30 epoch, ảnh 640 px, batch 8, CPU 4 thread, seed 42, cùng AdamW, learning rate,
augmentation và quy tắc chọn checkpoint bằng mAP50–95 validation. Không thay
ngân sách riêng cho Original hay Improved. Không dùng lượt YOLOv8n làm mốc gốc.

## Nguồn phương pháp

1. Woo, S., Park, J., Lee, J.-Y. và Kweon, I. S. (2018), **CBAM Convolutional
   Block Attention Module**, ECCV, tr. 3–19.
   [Bài gốc và PDF chính thức](https://www.ecva.net/papers/eccv_2018/papers_ECCV/html/Sanghyun_Woo_Convolutional_Block_Attention_ECCV_2018_paper.php).
   Triển khai theo phương trình 2–3: average/max pooling dùng chung MLP,
   reduction 16, attention kênh trước attention không gian, kernel 7×7.
2. Zhang, Y.-F., Ren, W., Zhang, Z., Jia, Z., Wang, L. và Tan, T. (2022),
   **Focal and efficient IoU loss for accurate bounding box regression**,
   Neurocomputing 506, tr. 146–157,
   [DOI 10.1016/j.neucom.2022.07.042](https://doi.org/10.1016/j.neucom.2022.07.042),
   [bản tác giả](https://arxiv.org/abs/2101.08158).
   Sử dụng EIoU tại phương trình 7, gồm IoU, khoảng cách tâm và sai lệch hai cạnh.
   Phần focal tại phương trình 10 không được đưa vào cấu hình này. DFL, loss
   phân lớp và task-aligned assignment của YOLO11n được giữ nguyên.
3. **CBAM-Enhanced YOLO11n A Lightweight and Efficient Model for Solid Waste
   Detection Compared to YOLOv9n YOLOv10n and RT-DETR**, ICITRI 2025,
   [DOI 10.1109/ICITRI67507.2025.11232874](https://doi.org/10.1109/ICITRI67507.2025.11232874).
   Đây là tài liệu liên quan trực tiếp đến YOLO11n và rác. Phiên làm việc hiện
   truy cập được tóm tắt của nhà xuất bản; chưa có đủ toàn văn để tuyên bố tái
   hiện chính xác cấu hình hay số liệu trong bài này.

`improvements.py` chứa mã riêng của project. Thư viện Ultralytics cài trên máy
được giữ nguyên. Trước train, `initialization.json` ghi hash của toàn bộ tensor
gốc; cả bốn cấu hình của một bộ phải có cùng hash. Chỉ CBAM bổ sung tham số;
thay loss bằng EIoU không thêm tham số suy luận. Các kiểm tra công thức, gradient,
serialization và train/predict ngắn đã chạy trước huấn luyện dữ liệu thật.

## Hồ sơ và giới hạn

Thư mục: `outputs/yolo11-original-improved-20261116`.

- `study_plan.json`: thiết kế và các yếu tố được khóa trước kết quả mới.
- `study_status.json`, `<bộ>/progress.json`: tiến độ thật.
- `<bộ>/<cấu hình>/results.csv`: nhật ký đủ 30 epoch.
- `<bộ>/<cấu hình>/weights/best.pt`: checkpoint chọn theo validation.
- `<bộ>/<cấu hình>/test_results.json`: số đo test, chỉ tạo sau khi đủ 12 lượt train.
- `comparison_original_improved.csv` và JSON: bảng 12 hàng, gồm mọi cải thiện
  và suy giảm. Đơn vị P/R/F1/mAP trong JSON/CSV là 0–1.

Giữ nguyên bản ảnh, nhãn và cách chia của ba bộ đã kiểm tra. Mỗi bộ là nhiệm vụ
phát hiện một lớp với phạm vi nhãn riêng. Cả ba tập test đã được đọc trong đợt
so sánh kiến trúc trước; giới hạn này được công bố. Đợt mới dùng một seed,
không khẳng định ý nghĩa thống kê hay tối ưu toàn cục. Các kiểm tra tổng hợp
trong thư mục smoke chỉ xác minh chạy phần mềm, không được dùng làm độ chính xác.

## Lệnh sử dụng từ ModelAI

Sau khi các lượt train đã hoàn tất, đo riêng hai cấu hình trên cùng test HAUI:

```powershell
& 'C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.14-64\python.exe' -m trashsmart.yolo_training.ablation --stage evaluate --dataset haui --variant original
& 'C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.14-64\python.exe' -m trashsmart.yolo_training.ablation --stage evaluate --dataset haui --variant improved
```

Thử ảnh độc lập, mỗi lệnh mở hộp chọn ảnh và ảnh kết quả:

```powershell
& 'C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.14-64\python.exe' -m trashsmart.yolo_training.ablation --stage predict --dataset haui --variant original --show
& 'C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.14-64\python.exe' -m trashsmart.yolo_training.ablation --stage predict --dataset haui --variant improved --show
```

Chọn cùng ảnh ở hai lần chạy, hoặc truyền `--image 'đường dẫn ảnh thật'` cho
cả hai lệnh. Thay `haui` bằng `taco` hoặc `uavvaste` để chọn cặp trọng số khác.
Kết quả đo lại được lưu riêng trong `rechecks` để giữ bản đo thực nghiệm ban đầu.

Tạo lại đợt nghiên cứu cần một thư mục mới, sau đó chạy điều phối:

```powershell
& 'C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.14-64\python.exe' -m trashsmart.yolo_training.ablation --stage prepare --root outputs/yolo11-ablation-new
& 'C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.14-64\python.exe' -m trashsmart.yolo_training.ablation --stage run --root outputs/yolo11-ablation-new
```
