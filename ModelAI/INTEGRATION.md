# TrashSmart — Tích hợp FE / BE / AI

API chính thức: `trashsmart.pipeline.main:app`. Các entry point `api:app`, `apiv2:app` và `app:app` cùng export một FastAPI để giữ tương thích với các lệnh chạy cũ.

```powershell
cd .\ModelAI
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Nếu `python` chưa nằm trong PATH, dùng đường dẫn interpreter đã cài, ví dụ máy này:

```powershell
& "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe" -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Môi trường phát triển hiện tại đã có các thư viện. Khi dựng môi trường mới, xem các requirements/lock tương ứng nền tảng và phiên bản Python; không cài lock Linux Python 3.10 vào Python 3.14 Windows. Cấu hình `.env` bằng thông tin Cloudinary hợp lệ và checkpoint phù hợp; không commit thông tin bí mật.

- `GET /live`: tiến trình đang chạy, không nạp model.
- `GET /metadata`: phiên bản hợp đồng, thứ tự nhãn, giới hạn ảnh và các ngưỡng triển khai; không nạp model.
- `GET /health`: kiểm tra nạp được cả YOLO và ResNet; 503 nếu checkpoint/môi trường lỗi.
- `POST /predict-image-url`: JSON `request_id` (số dương), `image_url` (URL HTTP/S public). BE bỏ qua `conf`/`iou` để sử dụng cấu hình triển khai AI.

Kết quả dùng camelCase: `apiVersion: "1"`, `requestId`, `annotatedUrl`, `count`, `confidenceAvg`, `requiresConfirmation`, `detections`. Mỗi detection gồm `label`, `labelDisplay`, `confidence`, `needsConfirm`, `x1/y1/x2/y2`, `cropUrl` khi có.

Nhãn vật liệu: `glass`, `metal`, `paper`, `plastic`; `unknown` là trạng thái không đủ tin cậy, không phải lớp thứ năm được huấn luyện. Confidence thuộc [0,1]. BE giữ nguyên nhãn và `needsConfirm` của AI, không dùng LLM hoặc vote để đổi dự đoán. FE hiển thị hướng dẫn tham khảo theo mã vật liệu và không đưa hướng dẫn cụ thể cho `unknown`.

YOLO là bộ phát hiện vị trí; ResNet phân loại vật liệu từ crop. Checkpoint và thứ tự lớp phải khớp metadata. Thay đổi lần này không huấn luyện lại hoặc sửa trọng số.

BE và AI có thể dùng cùng tài khoản Cloudinary. Ảnh gốc do BE upload phải có URL public để AI tải; cấu hình chặn URL nội bộ của AI được giữ nguyên. Nên chỉ mở dịch vụ AI trên mạng nội bộ/loopback sau BE.

```powershell
python -m unittest discover -s tests
```

Hướng dẫn vận hành toàn hệ thống và những điểm lệch đã sửa: `../../../BE/INTEGRATION.md` (từ thư mục dự án này).
