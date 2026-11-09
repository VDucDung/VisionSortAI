# HITL cho vật liệu từng bộ phận chai

Đã thêm xác nhận của người dùng, hàng đợi admin duyệt nhãn và lệnh chuẩn bị/huấn luyện vòng học mới. Đây là **active learning theo đợt**: hệ thống ưu tiên hỏi ở dự đoán chưa chắc chắn, thu nhãn có kiểm chứng, rồi học bằng phiên bản model riêng. Bấm “Gửi xác nhận” chưa cập nhật trọng số ngay.

## Sử dụng trên website

1. Người dùng mở Kết quả → Nhận diện chi tiết. Các bộ phận chưa chắc chắn mở sẵn mục hỏi vật liệu; bộ phận còn lại có thể mở để xác nhận/sửa nếu AI đoán sai.
2. Chọn Nhựa, Giấy, Kim loại, Thủy tinh hoặc Không chắc chắn. Không chọn sẵn đáp án để hạn chế ảnh hưởng từ dự đoán AI. Nêu cách kiểm chứng, xác nhận khung đúng và chọn có đồng ý dùng ảnh/xác nhận để học hay không. Có thể gửi phản hồi khi chưa đồng ý, nhưng phản hồi đó không được đưa vào dữ liệu train.
3. Admin đăng nhập và mở **Duyệt xác nhận**. Xem ảnh và khung bộ phận, dự đoán AI, câu trả lời và căn cứ. Nếu người dùng đã kiểm tra trực tiếp hoặc đọc ký hiệu bao bì, có thể duyệt như trước. Nếu người dùng chỉ xem hình, admin có thể chọn căn cứ riêng: đối chiếu hình ảnh, kiểm tra trực tiếp hoặc đọc ký hiệu; tích “Tôi xác nhận vật liệu người dùng chọn là đúng” và ghi chú để duyệt. Vật liệu vẫn phải biết rõ, vùng đúng và người dùng đồng ý dùng để học. Cần ghi lý do nếu không dùng để học. Admin không tự duyệt phản hồi của chính mình.
4. Xuất **nhãn đã duyệt** thành `hitl-approved-materials.json`. File xuất không chứa email, số điện thoại hoặc mật khẩu. File vẫn có URL ảnh để tạo crop huấn luyện; giữ trong project và chỉ dùng đúng mục đích đã được đồng ý.

Hiện tính năng chỉ xác nhận vật liệu trong khung đã có. Nếu AI khoanh sai vùng, bỏ chọn “Khung ảnh đánh dấu đúng bộ phận này”; vùng đó sẽ không được dùng để học. Các bộ phận AI bỏ sót hoàn toàn cần tiếp tục gán vùng bằng công cụ annotate hiện có; không biến ảnh gán thiếu thành annotation detector đầy đủ.

Căn cứ admin được lưu riêng ở `adminVerificationBasis`, cùng người duyệt, thời điểm và ghi chú. Không sửa `verificationBasis` ban đầu của người dùng. Khi xuất dữ liệu, đối chiếu ảnh được ghi rõ `ADMIN_VISUAL_REVIEW`, không ghi thành kiểm chứng vật liệu trực tiếp. Công cụ tạo dataset chấp nhận nhãn này khi có nguồn xác nhận admin; provenance gốc vẫn đi theo crop. Xác nhận bằng ảnh vẫn có thể nhầm vật liệu, vì vậy cần tiếp tục đánh giá bằng mẫu chai độc lập ở các vòng học.

## Chọn mẫu hỏi con người

- Ưu tiên hỏi nếu vật liệu `unknown`, confidence vật liệu dưới 0.8 hoặc confidence vùng dưới 0.6. Đây là ngưỡng vận hành ban đầu, không phải xác suất đúng đã hiệu chỉnh.
- Điểm sắp xếp là `1 - min(materialConfidence, detectionConfidence)`; `unknown` có điểm 1. Admin xem các mẫu ưu tiên cao trước.
- Các giá trị confidence của model vẫn giữ nguyên. Câu trả lời của người dùng được hiển thị riêng, không sửa ngược dự đoán/lịch sử cả chai.
- Snapshot được chống trùng theo lượt quét, detection, model version, loại bộ phận, vật liệu dự đoán và bbox. Phản hồi chỉ gửi một lần cho snapshot; revision và khóa DB chặn gửi/duyệt trùng và quyết định dựa trên bản cũ.
- Model hiện tại có thể tự tin nhưng sai; vì vậy cả bộ phận không được hệ thống chủ động hỏi cũng cho phép người dùng mở mục xác nhận.

Tham khảo cách hỏi nhãn dựa trên độ không chắc chắn và lưu ý người gán nhãn có thể sai trong [Burr Settles, Active Learning Literature Survey](https://burrsettles.com/pub/settles.activelearning.pdf). Chưa có đánh giá thực nghiệm chứng minh quy trình này đã tăng accuracy của project; cần có phản hồi thật và so sánh các vòng trên tập đánh giá cố định.

## Chuẩn bị đợt học

Giữ file xuất nguyên từ admin, không tự sửa các cờ `adminReviewed`/`trainingConsent`. Ví dụ lưu ở `BE\hitl-approved-materials.json`. Chạy lệnh trong terminal AI:

~~~powershell
cd D:\thacsi\DOAN\HAUI-TRASH\Model_AI\ModelFeatNew\Model_AI_Yolo
python -m trashsmart.components.hitl prepare --feedback D:\thacsi\DOAN\HAUI-TRASH\BE\hitl-approved-materials.json --base-data D:\thacsi\DOAN\HAUI-TRASH\AI_DATASET\bottle_components\05_models\components-experimental-v1\dataset --source-cache D:\thacsi\DOAN\HAUI-TRASH\AI_DATASET\bottle_components\03_public\taco-material-review\images --output D:\thacsi\DOAN\HAUI-TRASH\AI_DATASET\bottle_components\04_prepared\hitl-round-001
~~~

Công cụ chỉ nhận nhãn đã duyệt, có đồng ý, vùng đúng và có căn cứ kiểm chứng; chỉ tạo **crop train cho classifier vật liệu**. Ảnh bị đổi kích thước/bbox sai bị chặn; nhãn xung đột cùng một vùng làm dừng chuẩn bị. Các case/vùng ảnh trùng được bỏ qua. Toàn bộ ảnh nguồn của validation/test được so pHash để loại ảnh giống/gần giống khỏi train; giữ nguyên file crop và cách chia validation/test. Giới hạn: pHash không bảo đảm phát hiện mọi ảnh cùng một chai chụp ở góc khác, nên đây chưa phải benchmark theo sản phẩm vật lý độc lập.

Thư mục đầu ra phải mới. `dataset-report.json` lưu manifest và hash từng crop, SHA export và nguồn, số nhãn mới, lý do bỏ qua. Những ảnh nguồn holdout cần cho vòng sau được sao chép riêng; không được thêm vào ImageFolder train. Có thể dùng dataset của vòng trước làm `--base-data` cho vòng sau: nhãn cũ được giữ, số nhãn tối thiểu chỉ tính nhãn mới của vòng đó.

## Huấn luyện phiên bản riêng

Mặc định cần tối thiểu 20 crop HITL mới hợp lệ. Nếu chưa đủ, lệnh dừng trước khi train. Chưa có phản hồi thật nào được tự tạo từ các bài test; không giả lập việc model đã học từ người dùng.

~~~powershell
python -m trashsmart.components.hitl train --data D:\thacsi\DOAN\HAUI-TRASH\AI_DATASET\bottle_components\04_prepared\hitl-round-001 --release trashsmart\models\components-experimental-v1\experimental-release.json --output D:\thacsi\DOAN\HAUI-TRASH\AI_DATASET\bottle_components\05_models\components-hitl-round-001 --version components-hitl-round-001 --epochs 20 --threads 4
~~~

Lệnh dùng classifier hiện có để khởi tạo, giữ backbone ResNet18 đóng băng và học lại lớp cuối từ dữ liệu gốc + HITL. Lựa chọn checkpoint theo macro F1 validation; giữ cả checkpoint khởi đầu nếu các epoch mới không tốt hơn. Test chỉ đánh giá sau khi chọn checkpoint. Kiểm tra hash crop để phát hiện file bị thêm/sửa sau chuẩn bị. Kết quả gồm classifier, bản sao detector, evaluation và release riêng; `validated=false`, `experimental=true`, không tự kích hoạt hoặc ghi đè model cũ.

Chỉ cân nhắc chuyển sang phiên bản mới sau khi đọc evaluation và kiểm tra ảnh chai độc lập, đặc biệt nắp/nhãn/nhựa và vùng bị bỏ sót. Với vòng thử nghiệm đã kiểm tra, có thể chọn bản mới trong chính terminal AI, ví dụ:

~~~powershell
$env:DETAILS_RELEASE_PATH='D:\thacsi\DOAN\HAUI-TRASH\AI_DATASET\bottle_components\05_models\components-hitl-round-001\experimental-release.json'
python -m uvicorn trashsmart.pipeline.main:app --host 127.0.0.1 --port 8000
~~~

Để dùng lại bản chi tiết v1 mặc định: dừng AI bằng Ctrl+C, chạy `Remove-Item Env:DETAILS_RELEASE_PATH -ErrorAction SilentlyContinue`, rồi chạy lại lệnh uvicorn. Nhận diện cả chai vẫn dùng bộ trọng số cũ. Không có worker, scheduler hoặc dịch vụ train chạy nền được thêm vào project.

## API và dữ liệu

- `POST /api/v1/scans/{id}/detailed`: phân tích, lưu snapshot HITL vào bảng mới `component_learning_cases`, trả case ID và trạng thái phản hồi cho từng bộ phận. Không cập nhật bảng kết quả AI cũ.
- `GET /api/v1/scans/{id}/learning`: xem các snapshot của lượt quét, kiểm tra quyền owner/admin.
- `POST /api/v1/scans/{id}/learning/{caseId}/feedback`: chỉ chủ lượt quét; `material`, `verificationBasis`, `regionCorrect`, `trainingConsent`, `note`, `revision`. Không nhận bbox/dự đoán từ FE.
- `GET /api/v1/admin/learning?state=PENDING&page=0&size=20`: hàng đợi ưu tiên, có phân trang.
- `POST /api/v1/admin/learning/{caseId}/review`: `decision=APPROVE|REJECT`, `note`, `revision`; thêm `verificationBasis=VISUAL_REVIEW|PHYSICAL_CHECK|PACKAGING_MARK` và `confirmedCorrect=true` khi admin kiểm chứng riêng (ghi chú bắt buộc). Chỉ admin, kiểm tra điều kiện và người duyệt khác người gửi.
- `GET /api/v1/admin/learning/export?page=0&size=100`: chỉ nhãn đủ điều kiện đã duyệt, phân trang tối đa 100/lần.

Trạng thái: `OPEN → PENDING → APPROVED/REJECTED`. Lưu dự đoán gốc, model version, URL/box, người gửi, thời điểm gửi, căn cứ/đồng ý, người duyệt và thời điểm duyệt. Model chưa tự thay đổi khi chuyển trạng thái.
