# TrashSmart — Frontend

Giao diện HTML/CSS/JavaScript thuần, không cần cài thư viện. Yêu cầu Node.js 20 trở lên.

## Chạy local

```powershell
cd .\FE
node serve.mjs
```

- User: http://127.0.0.1:5173/User/index.html
- Admin: http://127.0.0.1:5173/Admin/login.html

Đổi địa chỉ backend tại `constants.js` (`apiBase`, mặc định `http://localhost:8080`). Chạy qua HTTP server; không mở bằng `file://`. Nếu dùng Live Server, mở đúng thư mục FE này. Server tích hợp dùng cổng 5173 để tránh nhầm với Live Server cũ trên 5500.

## Luồng sử dụng

User có ba trang chính: Trang chủ, Kết quả, Lịch sử. Đăng ký/đăng nhập bằng số điện thoại để quét và lưu lịch sử. Ảnh nhận JPG/PNG/WebP tối đa 10 MB, 12 megapixel, cạnh dài nhất 8192 px. Nút camera dùng tính năng chụp ảnh của trình duyệt/thiết bị.

Admin chỉ đăng nhập bằng email của tài khoản ADMIN được cấp tại BE; không có đăng ký admin. Các trang quản trị: Bảng điều khiển, Lịch sử quét, Thống kê, Quản lý người dùng và Tài khoản của tôi. Có tìm kiếm, bộ lọc ngày/vật liệu, phân trang, xem chi tiết, chỉnh thông tin và khóa/mở người dùng. Trang Tài khoản của tôi (`Admin/profile.html`) cho sửa họ tên, SĐT, email và đổi mật khẩu. Đổi email/mật khẩu cần mật khẩu hiện tại; phiên hiện tại được cập nhật, các token cũ hết hiệu lực.

Toàn bộ trang dùng `assets/app.js`, `assets/styles.css`, `assets/logo.svg`. Không còn số liệu mẫu hoặc logic quản lý quiz/model/bài viết trong giao diện đang dùng. Các đường dẫn trang cũ được chuyển về luồng mới.

`assets/app.js` chỉ khởi động ứng dụng; mã nguồn được chia theo chức năng trong `assets/src/`. `application.js` ghép các mô-đun `core`, `ui`, `features` và giữ trạng thái riêng cho từng trang. Xem [cấu trúc và quy tắc phát triển](../docs/PROJECT_STRUCTURE.md).

## Kết nối

FE chỉ gọi `/api/v1` của BE. Token User/Admin được tách riêng trong `sessionStorage`; BE kiểm tra quyền trên mọi yêu cầu. Lịch sử/kết quả được tải từ server bằng ID, không lấy từ cache local của giao diện cũ.

`confidence` hiển thị theo phần trăm từ giá trị 0–1 của model; đây không phải chỉ số độ chính xác đã đánh giá trên tập kiểm thử. Nhãn `unknown` hoặc `needsConfirm` được hiển thị cần kiểm tra thêm.

```powershell
node --check assets/app.js
```

Kiểm thử luồng giao diện (từ thư mục `FE`, sau khi cài devDependencies):

```powershell
npm.cmd ci
npm.cmd test
npm.cmd run test:annotator
```

Hướng dẫn API, cấu hình AI, tạo admin và kiểm thử liên tầng: `../BE/INTEGRATION.md`.
