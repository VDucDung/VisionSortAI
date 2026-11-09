# Triển khai bộ phận chai — 03/11/2026

## Đã có trong source

- AI: `trashsmart/components` gồm tải dữ liệu SPIN/PartImageNet, nhập annotation, kiểm kê, tool gán nhãn loopback, kiểm tra dữ liệu, export crop theo nhóm, huấn luyện YOLO11n detector và ResNet18 material baseline, đánh giá, đóng bundle và inference theo checkpoint được xác nhận.
- BE: entity `DetectionComponent` thuộc `Detection`; DTO/API v1 bổ sung dữ liệu bộ phận; kiểm tra confidence và khung nằm trong chai cha; lưu model version; truy vấn lịch sử theo cả vật liệu chai/bộ phận; thống kê bộ phận riêng. Hibernate `ddl-auto=update` tạo bảng/cột bổ sung khi khởi động BE.
- FE: kết quả phân cấp, chọn bộ phận đánh dấu khung trên ảnh gốc, trạng thái thiếu model, tương thích lịch sử cũ, thống kê/lịch sử và version tài nguyên chung `20261103-components`.
- CPU: `train-components-cpu.ps1`; Colab: `notebooks/bottle_components_colab.ipynb`; chỉ đóng gói code/crop/nhãn cần train, không có `.env` hay dữ liệu tài khoản.

## Trạng thái AI thực tế

Chưa có checkpoint bộ phận/vật liệu đã được kiểm chứng trên ảnh chai thật. Tính năng mới mặc định `PARTS_ENABLED=false`. Không đổi model chai cũ, không suy diễn giấy/kim loại từ hình dạng hoặc tên bộ phận.

SPIN có 483 ảnh chai kèm annotation subpart, nhưng không cung cấp vật liệu glass/metal/paper/plastic đã xác minh. Bản nhập tự động được để chờ rà soát, không tự đánh dấu đã gán đủ/đã kiểm tra. Các ảnh có nhiều whole/body không rõ quan hệ bị bỏ qua khi chuyển đổi. Xem số ảnh tải thực tế và lỗi tải tại `AI_DATASET/bottle_components/03_public/source-report.json`.

Script train được smoke test bằng fixture tổng hợp, một epoch, checkpoint tạm và không kích hoạt. Không dùng các chỉ số từ fixture làm độ chính xác cho đồ án. Cần rà soát annotation công khai, thu thập ảnh thật và xác minh vật liệu để train/evaluate ứng viên thực.

Đã bổ sung pilot detector thật một epoch từ nhãn hình học công khai: `04_prepared/public-detector-v1` có 402 train, 24 val, 49 test. Việc chấp nhận nhãn nguồn được ghi riêng, không tự xác minh vật liệu hoặc tuyên bố đã rà soát thủ công toàn bộ ảnh. Model tại `05_models/public-detector-pilot-v1` chưa bật trong app; cần huấn luyện/đánh giá thêm và có classifier vật liệu bộ phận. Epoch đầu khoảng 126,6 giây với CPU, ảnh 416, batch 2, 4 thread.

## Bước người dùng cần làm

Đọc `D:\thacsi\DOAN\HAUI-TRASH\AI_DATASET\bottle_components\README.md`.

1. Ảnh thật: `01_user_photos/images`; tên `bottle_001_front.jpg`, `bottle_001_back.jpg`…
2. Vật liệu: `01_user_photos/materials.csv`; mẫu điền tại `examples/materials.example.csv`.
3. Ảnh minh họa phân chia bộ phận: `examples/bottle_001_front.png` (không dùng train).
4. Giai đoạn đầu khoảng 20–30 mẫu chai để kiểm kê thiếu dữ liệu; đây không phải mức đủ để cam kết độ chính xác.

## Lệnh khởi động

```powershell
# BE: khởi động lại để nạp entity/API mới
cd D:\thacsi\DOAN\HAUI-TRASH\BE\hauiTrash
.\mvnw.cmd spring-boot:run

# AI: terminal khác, dùng Python đang cài dependencies project
cd D:\thacsi\DOAN\HAUI-TRASH\Model_AI\ModelFeatNew\Model_AI_Yolo
python -m uvicorn api:app --host 127.0.0.1 --port 8000

# FE: terminal khác
cd D:\thacsi\DOAN\HAUI-TRASH\FE
node serve.mjs
```

Tool gán nhãn chạy riêng: `python -m trashsmart.components annotate --data 'D:\thacsi\DOAN\HAUI-TRASH\AI_DATASET\bottle_components'`, rồi mở `http://127.0.0.1:8766`. Không tải ảnh ra ngoài. Chi tiết export, train CPU/Colab, resume và đánh giá/phát hành ở `Model_AI_Yolo/COMPONENTS.md`.

## Hợp đồng dữ liệu

Endpoint AI vẫn `/predict-image-url`, `apiVersion=1` với các trường mới tùy chọn, không có endpoint API v2 đang chạy. `count` luôn là số chai. `componentCount` riêng; `detections[].components[]` có `partType`, `material`, hai confidence và `x1,y1,x2,y2` trên ảnh gốc. BE bổ sung tên tiếng Việt, hướng dẫn và trạng thái. Không dùng điểm confidence cả chai cho bộ phận.

Lượt DONE giữ nguyên khi retry, tránh tự thay lịch sử khi thay model. Sau khi bật checkpoint mới, tạo lượt quét mới để phân tích bộ phận. Phiên đăng nhập và kiểm tra quyền sở hữu vẫn áp dụng.
