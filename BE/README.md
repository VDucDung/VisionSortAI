# TrashSmart — Backend

Backend Spring Boot 3.5.9 / Java 21 cho nhận diện và phân loại vật liệu, lịch sử quét và quản trị người dùng.

Chạy từ thư mục `BE`:

```powershell
cd .\hauiTrash
.\mvnw.cmd clean spring-boot:run
```

Cần MySQL và database `HauiTrash`, cấu hình `hauiTrash/application-local.properties`. File cấu hình hiện có đã được giữ lại; khi thiết lập máy mới, xem `hauiTrash/application-local.example.properties`. AI chạy tại cổng 8000; backend mặc định 8080; FE tại 5173.

[Hướng dẫn toàn hệ thống, cấp admin, API và kết quả kiểm thử](INTEGRATION.md).

```powershell
cd .\hauiTrash
.\mvnw.cmd clean test
```

Kiểm thử khởi động/tích hợp dùng H2 tạm, không dùng MySQL thật. Không commit `application-local.properties` hoặc thông tin bí mật.