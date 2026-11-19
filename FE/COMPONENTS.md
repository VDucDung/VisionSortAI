# Kết quả bộ phận chai

FE giữ ba trang user và shell/header chung. Kết quả bổ sung các bộ phận trong từng thẻ chai; bấm một bộ phận để xem khung trên ảnh gốc. Số chai và số bộ phận được đếm riêng. Lịch sử và thống kê admin phân biệt vật liệu cả chai với vật liệu bộ phận.

Model chưa được đánh giá/bật sẽ không có dự đoán bộ phận. `NOT_RUN` là chưa phân tích; `MODEL_UNAVAILABLE` là model chưa sẵn sàng; `FAILED` là lỗi phân tích bộ phận; `COMPLETED` với danh sách rỗng là đã chạy nhưng chưa tìm được bộ phận phù hợp. Không có ba dòng vật liệu mặc định.

Chạy FE như cũ bằng `node serve.mjs`; dependencies chỉ dùng cho kiểm thử. Với Node.js 24:

```powershell
npm ci
npm test
```

Các test dùng DOM giả lập, mock BE và kiểm tra header, phiên đăng nhập, WebP, kết quả bộ phận, khung tương tác, lịch sử và thống kê. Không thay thế kiểm tra trực quan responsive trên trình duyệt và đánh giá AI bằng ảnh thật.

Hướng dẫn dữ liệu/huấn luyện: `../ModelAI/COMPONENTS.md`.
