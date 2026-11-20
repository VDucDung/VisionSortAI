# Cấu trúc mã nguồn VisionSortAI

Các lệnh khởi động trong README từng phần vẫn sử dụng được. Refactor cấu trúc không thay đổi URL trang, endpoint, DTO, ngưỡng nhận diện hoặc quy trình thực nghiệm.

## Frontend

```text
FE/
  User/, Admin/              Các trang HTML và đường dẫn công khai
  assets/
    app.js                   Entry point gọi mountApplication(window)
    src/
      application.js         Ghép các mô-đun và điều phối trang
      core/runtime.js        Cấu hình, phiên đăng nhập, HTTP client
      ui/ui.js               Layout, biểu tượng, định dạng, thông báo
      features/
        auth.js              Đăng nhập, đăng ký và hộp thoại đăng nhập
        scan.js              Chọn/chụp ảnh và gửi lượt quét
        results.js           Kết quả, bộ phận, nhận diện chi tiết
        history.js           Bộ lọc và lịch sử quét
        learning.js          Phản hồi vật liệu và duyệt nhãn HITL
        statistics.js        Dashboard và thống kê quản trị
        users.js             Quản lý người dùng
        profile.js           Hồ sơ quản trị
  tests/                     Kiểm thử DOM với chính các ES module
```

Mỗi lần `mountApplication(window)` tạo một context riêng. `runtime` sở hữu `session` và `account`; các feature sử dụng giá trị hiện tại qua context, tránh giữ bản sao phiên cũ sau đăng nhập/đổi hồ sơ. Các factory không truy cập DOM hoặc gọi API tại thời điểm import. Các phụ thuộc giữa feature được thể hiện bằng `context.results`, `context.learning`, v.v.; chỉ các hàm được mô-đun khác dùng mới xuất ra context.

Giữ `assets/app.js` mỏng. Khi bổ sung trang, thêm feature tương ứng rồi nối tại `application.js`. FE gọi BE qua `runtime.api`, không gọi trực tiếp AI hoặc tự thay đổi dự đoán. Không cần bundler hoặc thư viện chạy mới.

## Backend

```text
controller/                  Giao thức HTTP và kiểm tra đầu vào
security/                    Xác thực và phân quyền
service/                     Điều phối nghiệp vụ, giao dịch và trạng thái
mapper/
  ScanPredictionMapper.java  Kiểm tra hợp đồng AI, ánh xạ prediction vào entity
  ScanResponseMapper.java    Entity -> DTO kết quả và hướng dẫn vật liệu
client/                      Kết nối dịch vụ bên ngoài
repository/, entity/         Truy cập và biểu diễn dữ liệu
dto/                         Hợp đồng đầu vào/đầu ra
```

Luồng quét: controller → `ScanService` → `YoloClient`; sau khi AI trả kết quả, `ScanPredictionMapper` kiểm tra confidence/bộ phận/bounding box và ghi vào entity trong giao dịch do service quản lý. `ScanResponseMapper` dựng DTO cho FE. Hai mapper không gọi repository hoặc dịch vụ mạng.

`ScanService` giữ kiểm tra chủ sở hữu, chống xử lý trùng, giao dịch và ghi trạng thái lỗi/thử lại. Không đưa cuộc gọi mạng vào giao dịch cơ sở dữ liệu đang khóa lượt quét. `toDetail` và `status` trên service được giữ để các service hiện có tiếp tục dùng được.

Các luồng nghiệp vụ khác và các API trước đây giữ nguyên package hiện có; khi sửa chúng, tiếp tục áp dụng ranh giới controller/service/mapper/client thay vì thêm phép biến đổi DTO vào controller.

## ModelAI

```text
trashsmart/
  pipeline/
    main.py                  Entry point ASGI/CLI và hàm Python tương thích
    application.py           Ghép FastAPI, admission middleware và /details
    routes.py                HTTP adapters và xử lý lỗi của endpoint
    schemas.py               Pydantic request schemas
    runtime.py               Tải lười model và khóa suy luận
    inference.py             YOLO -> ResNet -> kết quả, bộ phận tùy chọn
    storage.py               Upload Cloudinary
    cli.py                   Chạy pipeline trên ảnh local
    input_limits.py          Tải/đọc ảnh và giới hạn đầu vào
    config.py, models.py      Cấu hình và loader trọng số
    utils.py                 Tiền xử lý và vẽ kết quả
  components/                Nhận diện bộ phận, chi tiết và HITL
  training/                  Huấn luyện classifier
  yolo_training/             Thực nghiệm detector Original/Improved
  shared/                    Thành phần được các pipeline sử dụng chung
```

`create_app` nhận các callable `get_models`, `process_image`, `download_image_to_cv2`. Router không sở hữu model. Các endpoint dự đoán vẫn là hàm đồng bộ để FastAPI chạy công việc chặn trong thread pool; health dùng limiter riêng, liveness/metadata không phải chạy suy luận. `ModelRuntime` giữ model theo tiến trình và đảm bảo tải một lần khi có yêu cầu đồng thời.

Entry point `api:app`, `apiv2:app`, `app:app`, `trashsmart.pipeline.main:app`, cùng `python -m trashsmart.pipeline.main` được giữ. YOLO/ResNet, tiền xử lý, TTA/NMS, ngưỡng xác nhận và cấu trúc kết quả không thay đổi.

Trong lúc thực nghiệm đang chạy, không chỉnh mã `yolo_training`, `training`, `shared`, cấu hình/chia tập dữ liệu hoặc checkpoint của lượt chạy đó. Các tiến trình con sẽ đọc mã nguồn từ đĩa khi bắt đầu lượt kế tiếp.

## Kiểm chứng

Từ `FE`:

```powershell
npm.cmd test
npm.cmd run test:annotator
```

Từ `BE/hauiTrash`, dùng JDK 21:

```powershell
.\mvnw.cmd test
```

Từ `ModelAI`, với interpreter có các dependency AI và `python-docx` cho kiểm tra tài liệu:

```powershell
python -m unittest discover -s tests
```

Máy hiện tại có interpreter AI Python 3.14 và interpreter tài liệu Python 3.12 riêng. Đợt refactor ngày 19/11/2026 chạy bộ test AI và test tính toàn vẹn DOCX riêng trên hai interpreter; chi tiết và log ở `ModelAI/outputs/project-refactor-20261119/`. Không cài thêm dependency hoặc thay môi trường của training để phục vụ refactor.
