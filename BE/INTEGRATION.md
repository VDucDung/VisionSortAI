# TrashSmart — Kết nối và vận hành

## Các điểm lệch đã sửa

- Thay toàn bộ giao diện User/Admin bằng một bộ thiết kế, một logo và một shell dùng chung. Ba trang User: Trang chủ, Kết quả, Lịch sử. Admin: Bảng điều khiển, Lịch sử quét, Thống kê, Quản lý người dùng; đăng nhập bằng email, không đăng ký admin.
- Thay admin controller cũ quản lý quiz/bài viết/thùng rác bằng API thống kê, lịch sử quét và quản lý người dùng. Các API tính năng cũ, mạng xã hội, WebSocket và route suy luận cũ không còn nằm trong allowlist của cấu hình bảo mật. Mã nguồn dịch vụ cũ còn được giữ để tránh xóa dữ liệu/chức năng ngoài phạm vi chuyển đổi; không được FE mới sử dụng.
- FE gọi BE, BE gọi đúng `/predict-image-url` của AI. BE không còn ép `conf=0.25`, `iou=0.60` lên cấu hình model. Ví dụ cấu hình triển khai hiện tại của model dùng ngưỡng phát hiện khác nên việc ép ngưỡng trước đây đã làm lệch hành vi.
- Mã vật liệu thống nhất: `glass`, `metal`, `paper`, `plastic`; `unknown` là kết quả chưa đủ tin cậy. Giữ nhãn và `needsConfirm` từ AI. Luồng mới không dùng RAG/LLM hay phản hồi cộng đồng để đổi dự đoán.
- Lưu trạng thái `UPLOADED`, `PROCESSING`, `DONE`, `ERROR` và ảnh đánh dấu ở cấp lượt quét. Lượt không có vật thể vẫn hoàn tất và có thể xem lại. Lỗi AI được lưu để thử lại cùng ID; lượt đã hoàn tất không suy luận hoặc tạo vật thể trùng khi bấm lại. Lượt xử lý bị gián đoạn có thể thử lại sau 5 phút.
- Kiểm tra chủ sở hữu ở BE khi đọc/thử lại lượt quét. ADMIN được xem toàn hệ thống; USER chỉ xem dữ liệu của mình. Token của tài khoản bị khóa bị từ chối ngay ở request kế tiếp. Quản lý người dùng không cho sửa tài khoản ADMIN hoặc nâng role qua request.
- Cùng giới hạn ảnh trên luồng FE/BE: JPG/PNG/WebP, tối đa 10 MB, 12 MP, cạnh dài nhất 8192 px. BE kiểm tra định dạng/kích thước thật trước khi upload, không chỉ tin MIME của trình duyệt. AI vẫn hỗ trợ thêm định dạng cho client riêng.
- Phân trang/tìm kiếm/lọc được xử lý tại BE. Thống kê lấy dữ liệu thật; khoảng ngày và biểu đồ theo UTC+7. Tổng người dùng là toàn hệ thống; các chỉ số quét/vật thể theo khoảng lọc (mặc định 30 ngày).
- Dùng MySQLDialect phù hợp Hibernate hiện tại, tắt tự chèn dữ liệu bài viết/quiz mẫu, tắt Open Session in View. Thêm giới hạn upload, timeout gọi AI và CORS theo cấu hình.
- Chuyển thông tin bí mật BE khỏi mã nguồn sang `hauiTrash/application-local.properties` được Git bỏ qua; giữ lại cấu hình máy hiện có. File mẫu không có khóa thật: `hauiTrash/application-local.example.properties`.

## Chạy ba thành phần

Mở ba terminal riêng. Bật MySQL, tạo database `HauiTrash` nếu chưa có. Backend yêu cầu JDK 21. Cấu hình database/Cloudinary/JWT nằm trong `hauiTrash/application-local.properties`; các giá trị cũ của máy đã được giữ lại. Hibernate cập nhật thêm cột cho bảng `ai_requests`; không có thao tác xóa dữ liệu cũ.

AI:

```powershell
cd D:\thacsi\DOAN\HAUI-TRASH\VisionSortAI\ModelAI
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Máy này có Python tại `$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe`; dùng đường dẫn đầy đủ nếu lệnh `python` không được nhận diện. `.env` AI phải trỏ đúng checkpoint và có thông tin Cloudinary hợp lệ. Kiểm tra `http://127.0.0.1:8000/metadata` và `/health`.

BE:

```powershell
cd D:\thacsi\DOAN\HAUI-TRASH\VisionSortAI\BE\hauiTrash
.\mvnw.cmd clean spring-boot:run
```

FE:

```powershell
cd D:\thacsi\DOAN\HAUI-TRASH\VisionSortAI\FE
node serve.mjs
```

User: http://127.0.0.1:5173/User/index.html  
Admin: http://127.0.0.1:5173/Admin/login.html

FE mặc định gọi `http://localhost:8080`; đổi `FE/constants.js` khi đổi BE. BE đọc `AI_BASE_URL` (mặc định `http://localhost:8000`) và `CORS_ORIGINS` khi triển khai khác local. Không mở trang bằng `file://`. Dùng đúng thư mục FE; cổng 5173 của server tích hợp tránh nhầm với một Live Server cũ trên 5500.

## Cấp tài khoản quản trị

Tài khoản ADMIN có sẵn vẫn đăng nhập được. Bước cấp tài khoản mặc định **tắt**, độc lập với việc chạy BE thông thường: các biến `ADMIN_EMAIL`, `ADMIN_PHONE`, `ADMIN_PASSWORD`, `ADMIN_UPDATE_EXISTING` còn từ lần thiết lập trước không tự tạo/cập nhật tài khoản và không làm BE ngừng khởi động.

Khi cần tạo admin, dùng script tại thư mục `BE` để nhập mật khẩu trực tiếp trong terminal, không ghi mật khẩu vào lệnh:

```powershell
# Dừng BE đang chạy trước bằng Ctrl+C.
cd D:\thacsi\DOAN\HAUI-TRASH\VisionSortAI\BE
powershell -NoProfile -ExecutionPolicy Bypass -File .\create-admin.ps1 -Mode New
```

Script tự bật `--app.admin.bootstrap-enabled=true` chỉ cho lần chạy cấp admin đó. Số điện thoại mới bắt đầu bằng 0 và có 10–11 chữ số; email và số điện thoại phải đều chưa được dùng; mật khẩu ít nhất 8 ký tự, tối đa 72 byte UTF-8. Khi bật cấp admin, cấu hình xung đột vẫn bị từ chối rõ ràng và không sửa dữ liệu. Admin đã tồn tại không bị đổi mật khẩu nếu chưa chủ động chọn cập nhật. Không có tài khoản/mật khẩu quản trị mặc định trong source.

Nếu chủ động muốn chuyển một tài khoản có sẵn thành ADMIN và đặt mật khẩu mới, chọn chế độ cập nhật rõ ràng:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\create-admin.ps1 -Mode UpdateExisting
```

Chế độ này chọn **duy nhất theo email được nhập**, giữ nguyên số điện thoại, thông tin và lịch sử của tài khoản; không gộp hai tài khoản. Tài khoản đang bị khóa không được cập nhật. Bên trong script dùng `ADMIN_UPDATE_EXISTING=true`, bỏ `ADMIN_PHONE` để giữ nguyên số điện thoại cũ, và lấy mật khẩu mới qua lời nhắc ẩn. Script khởi động BE, hiển thị kết quả cấp quyền trong log và giữ BE chạy để đăng nhập; khi dừng, các biến môi trường của script được khôi phục. Lần sau chạy BE bằng lệnh bình thường. Sau khi chuyển thành ADMIN, tài khoản đó đăng nhập ở khu vực admin bằng email; tài khoản USER khác không bị thay đổi.

## API đang dùng

Admin có thêm trang **Tài khoản của tôi** tại `FE/Admin/profile.html`, truy cập từ thanh bên hoặc nhấn tên/avatar trên header. Admin sửa họ tên, SĐT và email; khi đổi email cần xác nhận mật khẩu hiện tại. Form đổi mật khẩu yêu cầu mật khẩu hiện tại và nhập lại mật khẩu mới.

- `GET /api/v1/admin/profile`: hồ sơ của chính admin đang đăng nhập.
- `PATCH /api/v1/admin/profile`: `fullName`, `phone`, `email`, `currentPassword` (bắt buộc khi đổi email).
- `POST /api/v1/admin/profile/password`: `currentPassword`, `newPassword` (ít nhất 8 ký tự, tối đa 72 byte UTF-8).

Hai API ghi trả `AuthResponse` gồm token mới và thông tin tài khoản; FE cập nhật phiên hiện tại và tên trên header ngay khi lưu. Email/SĐT trùng bị từ chối; request không nhận ID/role để sửa admin khác. Đổi email hoặc mật khẩu tăng `accounts.token_version`, khiến các JWT cũ không còn hiệu lực; token thay thế của trang hiện tại vẫn dùng được. JWT cũ chưa có claim phiên bản được coi là phiên bản 0 để giữ tương thích lúc triển khai. Hibernate tự thêm cột có giá trị mặc định 0 khi BE khởi động bằng cấu hình `ddl-auto=update` hiện tại. Cập nhật mật khẩu qua bootstrap cũng vô hiệu hóa token cũ. Mật khẩu và token được loại khỏi biểu diễn log của DTO liên quan.

Sau khi cập nhật source, dừng BE bằng Ctrl+C và chạy lại `.\mvnw.cmd clean spring-boot:run` tại `BE/hauiTrash`. FE dùng phiên bản tài nguyên `20261101-profile`; nếu BE chưa được khởi động lại, trang hồ sơ sẽ báo rõ BE chưa hỗ trợ API mới thay vì thông báo sai quyền.

- `POST /api/v1/auth/register`: chỉ tạo USER, body `phone`, `fullName`, `password`.
- `POST /api/v1/auth/login/user` hoặc `/login/admin`: body `identifier`, `password`; user dùng điện thoại, admin dùng email. Response `{message,data:{token,account,...}}`.
- `GET /api/v1/auth/me`: tài khoản hiện tại.
- `POST /api/v1/scans`: multipart `file`, upload và phân tích, trả kết quả đã lưu.
- `GET /api/v1/scans`: lịch sử của người đang đăng nhập.
- `GET /api/v1/scans/{id}`: kết quả chi tiết; chủ sở hữu hoặc ADMIN.
- `POST /api/v1/scans/{id}/retry`: xử lý lại lượt lỗi/chờ/gián đoạn, giữ nguyên ID.
- `GET /api/v1/admin/scans`: lịch sử toàn hệ thống.
- `GET /api/v1/admin/statistics`: tổng quan, chuỗi thời gian và phân bố vật liệu.
- `GET /api/v1/admin/users`: tìm kiếm/phân trang người dùng.
- `PATCH /api/v1/admin/users/{id}`: `fullName`, `phone`, `email`, `active`.

Các API ngoài auth nhận `Authorization: Bearer <token>`. Danh sách trả `{items,total,page,size,totalPages}`, trang bắt đầu từ 0. Bộ lọc lượt quét: `q`, `material`, `from`, `to` (ngày ISO `yyyy-MM-dd`, bao gồm ngày kết thúc). Thống kê nhận `from/to`, tối đa 366 ngày. Confidence thuộc [0,1]; UI nhân 100 để hiển thị, không coi đây là độ chính xác đánh giá của model.

## Kiểm thử và giới hạn xác minh

Ngày 01/11/2026: sửa fixture `UploadErrorHttpTest` dùng `System.nanoTime() % 10000000` làm số điện thoại, khiến một số lần `clean package` thất bại do thiếu chữ số. Dùng bộ đếm bắt đầu từ bảy chữ số để dữ liệu kiểm thử hợp lệ và ổn định. Sau sửa, `clean package` qua toàn bộ 35 kiểm thử; chạy thử đúng `mvnw.cmd clean spring-boot:run` bằng Java 21 với MySQL local đã thành công và `/api/v1/system/info` trả HTTP 200. Tiến trình kiểm tra đã được dừng để không chiếm cổng 8080 khi người dùng chạy BE trong terminal.

BE có kiểm thử tích hợp H2 cho đăng ký/đăng nhập, vai trò, CORS, cách ly dữ liệu, lọc lịch sử, trạng thái xử lý, retry, thống kê, khóa phiên và upload ảnh không hợp lệ; kiểm thử khởi động dùng H2 thay vì MySQL thật.

```powershell
cd D:\thacsi\DOAN\HAUI-TRASH\VisionSortAI\BE\hauiTrash
.\mvnw.cmd clean test
```

AI có kiểm thử API, metadata, admission, giới hạn ảnh, checkpoint và workflow huấn luyện. Lần kiểm tra tích hợp cũng nạp model thật và suy luận ảnh mẫu local; upload được giả lập trong bước kiểm tra này. Không huấn luyện lại hay đánh giá lại độ chính xác trên tập test độc lập.

Kiểm thử FE hiện nằm trong `FE/tests/frontend-flow-tests.mjs` và `FE/tests/annotator-flow-tests.mjs`. Chạy `npm.cmd test` và `npm.cmd run test:annotator` từ thư mục `FE` sau khi cài devDependencies. Các bản kiểm thử cũ trong `.integration` chỉ là hồ sơ local. Kiểm thử DOM không thay thế việc kiểm tra bố cục bằng mắt trên các kích thước thiết bị thực.

Sửa lỗi chọn ảnh/đăng nhập: grid trang chủ dùng `minmax(0,1fr)` và các cột được phép co; tên file dài được rút gọn, có tooltip đầy đủ. Khi cần đăng nhập, hộp thoại mở ngay trên trang và giữ ảnh trong bộ nhớ; đăng nhập thành công tiếp tục gửi ảnh. FE không tự xóa phiên/chuyển sang login khi nhận một lỗi upload. Nếu BE trả 401 cho upload, FE kiểm tra riêng `/auth/me` trước khi yêu cầu đăng nhập lại. BE cho phép dispatcher `ERROR` đi qua để giữ đúng 500/404 thay vì biến thành 401. Đã tái hiện hai lỗi 500→401 và 404→401 bằng HTTP với server nhúng, sau sửa cả ba kiểm thử HTTP lỗi và sáu kiểm thử tích hợp phân quyền/luồng quét đều qua. Không có upload thật ra Cloudinary trong các kiểm thử này.

Bản `20261031-r3`: kiểm tra tiến trình thực tế phát hiện BE cổng 8080 còn chạy từ 15:06 và AI từ 14:56, trước các thay đổi tích hợp. Đã thay bằng JAR Java 21 vừa build (35 kiểm thử BE đều qua), khởi động lại AI và chuyển FE cổng 5500 từ Python HTTP server sang server Node có `Cache-Control: no-store`. Thời điểm chuyển đổi giữ nguyên hostname/cổng FE để không đổi nơi lưu phiên đăng nhập của trình duyệt. Ba trang User và tài nguyên có query phiên bản để không trộn HTML/module cũ; shell/header được dựng trước khi gọi API xác thực và vẫn hiển thị khi có lỗi. `GET /api/v1/system/info` là dấu hiệu công khai để FE nhận biết BE hỗ trợ `scanApiVersion:1`; FE kiểm tra trước khi upload và giữ ảnh nếu phát hiện BE cũ. Đã kiểm tra HTTP của ba trang mới, API thông tin BE, metadata AI và `/health` trả `modelsReady:true`. Chưa chạy một lượt upload thật lên Cloudinary khi chưa có chấp thuận cụ thể.

Địa chỉ của phiên đang chạy: `http://localhost:5500/User/index.html?v=20261031-r3`. Các PID dịch vụ và log vận hành nằm trong thư mục local `.integration` (`current-runtime.json`, `runtime-be.log`, `runtime-ai-error.log`, `runtime-fe.log`). Nếu sau này dừng phiên này và chạy lại theo lệnh mặc định, Node FE sẽ dùng cổng 5173 như hướng dẫn phía trên.

Kết quả kiểm tra thực tế: 30 kiểm thử BE và một kiểm thử hợp đồng HTTP YoloClient; 109 kiểm thử AI; 12 luồng FE bằng DOM. HTTP local đã xác minh `/metadata`, `/health` với cả hai checkpoint nạp được, đăng ký/đăng nhập USER, lịch sử và chặn USER truy cập admin. Mọi tài khoản trong bước kiểm tra HTTP được tạo trong H2 tạm.

Suy luận thật trên bốn ảnh mẫu: ảnh nhựa trả `plastic`, ảnh thủy tinh trả `glass`; ảnh kim loại trả `unknown` cần xác nhận, ảnh giấy không phát hiện vật thể. Đây là quan sát smoke test; cần một tập đánh giá riêng nếu muốn đo/cải thiện chất lượng checkpoint. Không có cơ sở công bố độ chính xác 98% như giao diện cũ.

Lượt upload ảnh thật lên Cloudinary chưa chạy: hệ thống duyệt tự động yêu cầu chấp thuận cụ thể cho ảnh `anh-chai-nhua.png` và nơi nhận Cloudinary. Kiểm thử suy luận local đã mock upload; không được xem bước đó là xác minh Cloudinary thực tế. Kiểm tra bố cục bằng trình duyệt cũng chưa hoàn tất do cửa sổ đang có thao tác của người dùng; các luồng FE được kiểm tra bằng DOM.

FE cũ và các file AI được sửa có bản lưu tại `BE/.integration/originals`. Thư mục này không phải bản sao cơ sở dữ liệu; dữ liệu MySQL không được sao lưu/xóa bởi tác vụ này.

Kiểm thử chức năng hồ sơ admin: toàn bộ 52 kiểm thử BE và 26 luồng FE qua. Kiểm thử BE dùng H2, xác nhận chặn USER, chỉ sửa admin đang đăng nhập, chống email/SĐT trùng, yêu cầu mật khẩu hiện tại, đổi mật khẩu và vô hiệu hóa token trước đó, giữ token thay thế dùng được và không đưa mật khẩu/token vào biểu diễn log. Không đổi thông tin hoặc mật khẩu của tài khoản MySQL thật trong quá trình kiểm tra.

Ngày 02/11/2026: sửa lỗi AdminBootstrap làm BE tắt khi còn cấu hình cấp admin cũ xung đột email/SĐT. Thêm app.admin.bootstrap-enabled (mặc định false, đọc ADMIN_BOOTSTRAP_ENABLED) để khởi động thông thường không thực hiện cấp quyền/đổi mật khẩu. create-admin.ps1 bật cờ bằng tham số riêng chỉ cho lần cấp admin. Giữ nguyên các kiểm tra xung đột khi chủ động bật cấp tài khoản. Toàn bộ 54 kiểm thử qua; kiểm thử khởi động với hai tài khoản H2 xung đột xác nhận không có tài khoản, quyền, mật khẩu hoặc phiên nào bị thay đổi. Chạy thử với MySQL thật trên cổng riêng 18080 và cấu hình admin giả không hợp lệ: BE bỏ qua cấp admin, đạt trạng thái sẵn sàng và API system/info trả HTTP 200; đã dừng tiến trình thử.

Ngày 02/11/2026: thêm WebP cho toàn luồng. FE cho chọn .webp/image/webp và xử lý trường hợp MIME bị trống trên Windows. BE dùng ImageIO WebP plugin của [TwelveMonkeys 3.15.3](https://github.com/haraldk/TwelveMonkeys/releases/tag/twelvemonkeys-3.15.3), kiểm tra kích thước trước khi giải mã rồi xác nhận ảnh hợp lệ. File gốc được chuyển nguyên byte cho uploader; không bắt người dùng đổi đuôi/chuyển định dạng. AI decoder hiện có hỗ trợ WebP, đã kiểm tra trực tiếp với ba ảnh tổng hợp lossy/lossless/alpha. Giới hạn 10 MB, 12 MP, cạnh dài nhất 8192 px giữ nguyên. Kiểm thử: 29 luồng FE, 7 kiểm thử validation/upload BE với upload mock, 3 kiểm tra decoder AI; không gửi ảnh thật ra ngoài. Cần khởi động lại BE và làm mới FE để nạp plugin/tài nguyên mới (20261102-webp).
