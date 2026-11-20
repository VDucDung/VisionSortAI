# VisionSortAI

Hệ thống TrashSmart gồm giao diện web, backend nghiệp vụ và dịch vụ AI nhận diện rác.

[Cấu trúc mã nguồn và quy tắc phát triển](docs/PROJECT_STRUCTURE.md) mô tả các mô-đun FE, tầng ánh xạ BE, dịch vụ suy luận ModelAI và cách kiểm thử.

- [FE](FE/README.md): giao diện HTML/CSS/JavaScript; chạy bằng `node serve.mjs` từ thư mục `FE`, mặc định cổng 5173.
- [BE](BE/README.md): Spring Boot / Java 21, cấu hình MySQL và thông tin kết nối trong tệp local của máy.
- [ModelAI](ModelAI/INTEGRATION.md): FastAPI; entry point chính `trashsmart.pipeline.main:app`. Các tệp `api.py`, `apiv2.py`, `app.py` giữ vai trò tương thích cho những lệnh chạy cũ.
- [Thực nghiệm Original và Improved](ModelAI/trashsmart/yolo_training/ORIGINAL_IMPROVED.md): bốn cấu hình YOLO11n trên HAUI, TACO và UAVVaste, cùng các lệnh chạy nhận diện độc lập.

Dữ liệu, nhật ký, checkpoint và kết quả thực nghiệm nằm trong `ModelAI/outputs/` và `ModelAI/runs/`. Các thư mục này chứa hồ sơ nghiên cứu, không phải toàn bộ đều là tệp tạm. Việc dọn cache cần giữ các snapshot dữ liệu, cấu hình, trọng số và báo cáo đánh giá tương ứng.

Tệp môi trường và `application-local.properties` là cấu hình riêng của máy. Dùng tệp `.example` khi thiết lập môi trường mới.

Các đợt dọn dẹp lưu danh sách thay đổi trong `ModelAI/outputs/project-cleanup-*/`. Những tệp nguồn cũ được loại khỏi luồng chính có bản khôi phục tại `.cleanup-archive/`; các cache tải xuống có thể tạo lại được liệt kê riêng trong biên bản.
