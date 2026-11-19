# Phương pháp cải tiến YOLO11n và thiết kế đối chứng

Tài liệu chuẩn bị phần phương pháp cho Chương 3. Các thông số dưới đây là
thiết kế đã khóa và số đếm kiến trúc đã kiểm tra. Kết luận về độ chính xác
sẽ được bổ sung từ các phép đo sau khi huấn luyện hoàn tất.

## Câu hỏi nghiên cứu và phần việc của đồ án

Thực nghiệm kiểm tra tác động của attention CBAM và hàm mất mát EIoU đối với
YOLO11n trong phát hiện rác. Phần việc của đồ án gồm chọn vị trí tích hợp ở
neck, triển khai hai thành phần trong mã nguồn, kiểm tra khởi tạo công bằng,
xây dựng ablation và đánh giá trên ba bộ dữ liệu. Hai kỹ thuật được dẫn nguồn
theo tác giả công bố; đóng góp ở đây là triển khai và kiểm chứng cho bài toán
của hệ thống.

## Mô hình gốc và ba biến thể

- **Original:** kiến trúc YOLO11n và thành phần CIoU gốc, train trên dữ liệu đích.
- **CBAM:** gắn attention vào ba đầu ra P3/P4/P5, giữ CIoU.
- **EIoU:** giữ kiến trúc gốc, thay thành phần CIoU của box regression bằng EIoU.
- **Improved:** kết hợp CBAM và EIoU. Đây là tên cấu hình đề xuất trước thực nghiệm;
  hiệu quả của nó cần được xác nhận bằng kết quả đo.

![Sơ đồ Original và Improved](../outputs/yolo11-original-improved-20261116/figures/architecture.png)

Transfer learning từ cùng checkpoint COCO áp dụng cho cả bốn cấu hình. Vì vậy,
bảng ablation ghi pretrained ở tất cả các hàng. Original chỉ kiến trúc và loss
nguyên bản; các siêu tham số train chung được công bố rõ để tách tác động của
CBAM và EIoU.

## CBAM tại ba mức đặc trưng

CBAM theo Woo và cộng sự, ECCV 2018, áp dụng attention kênh trước attention
không gian. Average pooling và max pooling dùng chung MLP với reduction 16;
nhánh không gian dùng convolution 7 × 7.
[Bài gốc và PDF chính thức](https://www.ecva.net/papers/eccv_2018/papers_ECCV/html/Sanghyun_Woo_Convolutional_Block_Attention_ECCV_2018_paper.php).

Trong bản YOLO11n đang sử dụng, CBAM được đặt sau C3k2 ở tầng 16, 19, 22 của
neck. Ba đầu ra có lần lượt 64, 128, 256 kênh, giữ nguyên giao diện với Detect
head. Kiểm tra cấu trúc cho bài toán một lớp ghi nhận Original có 2.590.035
tham số; cấu hình có CBAM có 2.601.081 tham số, tăng 11.046 tham số. Đây là số
đếm kiến trúc trước train, chưa phản ánh mức tăng độ chính xác.

## Thay thành phần định vị bằng EIoU

Sử dụng phương trình 7 trong bài của Zhang và cộng sự, *Neurocomputing* 506,
2022, tr. 146–157:

`L_EIoU = 1 − IoU + d²/(c_w² + c_h²) + (w − w_gt)²/c_w² + (h − h_gt)²/c_h²`.

Trong đó `d` là khoảng cách tâm; `c_w`, `c_h` là hai cạnh của khung nhỏ nhất
bao cả khung dự đoán và khung thật. DFL, loss phân lớp và task-aligned assignment
được giữ nguyên. EIoU chỉ thay loss train, không thêm tham số suy luận.
[DOI bài báo](https://doi.org/10.1016/j.neucom.2022.07.042),
[bản tác giả](https://arxiv.org/abs/2101.08158).

## Dữ liệu và ngân sách chung

- HAUI: 1.272 ảnh train, 372 validation, 182 test; 261 đối tượng test.
- TACO v0.2: 526 ảnh train, 97 validation, 92 test; 288 đối tượng test.
- UAVVaste: 541 ảnh train, 116 validation, 115 test; 616 đối tượng test.

Bốn cấu hình của từng bộ dùng cùng byte ảnh, nhãn và cách chia. Các nguồn có
phạm vi nhãn khác nhau và được diễn giải riêng. Hai bộ công khai gộp nhãn rác
thành một lớp item; khung lấy từ polygon nguồn đã kiểm tra hệ tọa độ.

Mỗi cấu hình train mới 30 epoch ở 640 px, batch 8, CPU 4 thread, seed 42. AdamW,
lr0 0,0005, cosine schedule và augmentation dùng chung. Mạng gốc được nạp trước
khi gắn CBAM; hash kiểm tra toàn bộ tensor gốc phải giống nhau giữa bốn cấu hình.
Khởi tạo CBAM giữ nguyên luồng RNG toàn cục. Các thay đổi nằm trong project,
không sửa thư viện Ultralytics đã cài.

## Đánh giá và bảng kết quả sẽ hoàn thiện

Checkpoint được chọn theo mAP50–95 validation trong cùng 30 epoch. Đánh giá
test bắt đầu sau khi đủ 12 lượt train. P/R/F1 dùng confidence 0,25, đối sánh IoU
0,50 và NMS IoU 0,70. AP dùng confidence 0,001 và TTA tắt.

Chương 3 sẽ có ba bảng ablation, mỗi bộ bốn hàng Original, CBAM, EIoU và
Improved, với dấu đánh dấu yếu tố, mAP50–95 và số tham số. Bảng chất lượng đầy
đủ bổ sung P/R/F1 và mAP50; bảng chi phí bổ sung checkpoint KiB và độ trễ CPU.
Chênh lệch được tính bằng điểm phần trăm, giữ cả giá trị âm. Các ảnh minh họa
Original/Improved dùng cùng đầu vào đã cố định trước kết quả mới.

## Giới hạn và bằng chứng

Đợt này dùng một seed. Cả ba tập test đã xuất hiện trong đợt so sánh kiến trúc
trước, nên không được mô tả là holdout mới. Box loss CIoU và EIoU có thang đo
khác nhau; đánh giá chất lượng dựa trên các chỉ số test chung. Thời gian CPU
chịu ảnh hưởng tải máy, nguồn điện và khoảng gián đoạn; các điều kiện được lưu
trong hồ sơ. Mọi kết luận về mức cải thiện phải dựa vào dữ liệu đo thực tế.

Nguồn liên quan trực tiếp đến rác là bài ICITRI 2025
[CBAM-Enhanced YOLO11n](https://doi.org/10.1109/ICITRI67507.2025.11232874).
Hiện chỉ xác minh được tóm tắt của nhà xuất bản; không tuyên bố tái hiện toàn
bộ cấu hình bài này. Hồ sơ phương pháp chi tiết và lệnh chạy nằm trong
[ORIGINAL_IMPROVED.md](../trashsmart/yolo_training/ORIGINAL_IMPROVED.md).
