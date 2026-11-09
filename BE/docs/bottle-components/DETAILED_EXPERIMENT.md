# Nhận diện chi tiết thành phần chai

Yêu cầu triển khai: giữ model và kết quả nhận diện cả chai, thêm tab “Nhận diện chi tiết”, huấn luyện classifier vật liệu ở một phiên bản riêng, có khả năng quay lại model trước.

Bổ sung HITL: xem [HITL.md](HITL.md) để xác nhận vật liệu, duyệt nhãn và chạy các vòng học riêng. Tab chi tiết hiện lưu thêm snapshot vào bảng HITL độc lập; kết quả/lịch sử nhận diện cũ không bị đổi nhãn. Không có dịch vụ AI hoặc train tự chạy nền; người dùng khởi động bằng terminal.

## Đã chuẩn bị

Model mới nằm ở `AI_DATASET/bottle_components/05_models/components-experimental-v1`. Classifier ResNet18 dùng backbone ImageNet đóng băng và học lớp cuối trong 75 epoch; chọn checkpoint ở epoch 18 theo validation. Đặc trưng được tính một lần vì backbone ở chế độ eval và phép biến đổi ảnh cố định. Detector nắp/thân/nhãn dùng bản nghiên cứu YOLO11n đã train 40 epoch trước đây, sao chép riêng vào thí nghiệm. Đây không phải việc train lại detector chai cũ.

Dữ liệu vật liệu gồm 252 crop lấy từ annotation TACO và 20 crop đã duyệt từ dữ liệu người dùng, tổng 272 crop. Chia tập: train 194, validation 40, test 38. Ảnh TACO được nhóm theo ảnh gốc, hash chính xác và độ gần perceptual hash trước khi chia; dữ liệu người dùng vẫn giữ train. Các lớp nguồn là Glass bottle, Metal bottle cap, Normal paper, Clear plastic bottle, Other plastic bottle, Plastic bottle cap. Normal paper là dữ liệu phụ trợ nhận diện giấy, không được mô tả thành nhãn chai đã kiểm chứng. Nguồn vật liệu là annotation tác giả hoặc khai báo người dùng; không giả định trợ lý đã kiểm tra vật liệu trực tiếp.

Test vật liệu trên 38 crop nguồn bổ sung: accuracy 0.7105, macro F1 0.6737. F1 từng lớp: glass 0.7000, metal 0.8000, paper 0.9091, plastic 0.2857. Đây là benchmark crop của nguồn dữ liệu bổ sung, **không phải độ chính xác phân tích mọi bộ phận trên ảnh chai thực tế**. Lớp nhựa còn yếu và cần thêm dữ liệu/cải thiện. Model chỉ phù hợp thử nghiệm, không đánh dấu validated production.

Checksum của `best_new.pt` và `best_resnet50_yolo.pth` đã đối chiếu, không thay đổi. Các file thí nghiệm có checksum riêng trong `experimental-release.json`; không ghi vào production `release.json` hoặc thay biến cấu hình model cũ.

## Luồng triển khai được viết

- BE: `POST /api/v1/scans/{id}/detailed` dùng quyền sở hữu/admin hiện có, lấy URL và tọa độ chai từ dữ liệu đã lưu. Không nhận tọa độ tùy ý từ FE. Response được kiểm tra ID chai, số bộ phận, mã vật liệu, confidence và bbox nằm trong chai.
- Dịch vụ AI chi tiết độc lập về model (mặc định mount /details trên 8000; tùy chọn chạy riêng 8011): `trashsmart.components.detail_api:app`. API nhận ảnh gốc và các chai đã phát hiện, dùng detector bộ phận và classifier mới. Không tải lại model chai cũ, không upload crop hoặc ảnh annotated lên Cloudinary. Giới hạn ảnh/URL công khai và chống quá tải dùng lại cơ chế hiện có.
- Model bộ phận thử nghiệm kiểm tra ảnh ở 4 góc quay, quy đổi bbox về ảnh gốc và loại khung trùng theo lớp. Một chai tối đa một thân, một nắp và bốn vùng nhãn. Mọi kết quả thử nghiệm đều cần kiểm tra lại; confidence thấp trả unknown. Đây là xử lý suy luận, chưa phải bằng chứng cải thiện độ chính xác end-to-end.
- FE có ba nút: Nhận diện, Ảnh gốc, Nhận diện chi tiết. Chỉ nút chi tiết gọi endpoint mới. Response được giữ trong phiên trang, không sửa số chai, confidence, ảnh annotated hoặc lịch sử của model cũ. Có trạng thái tải, lỗi/thử lại riêng, nhiều khung màu và chọn từng vùng. Response đến muộn không đổi tab người dùng đã chọn.

## Trạng thái triển khai và kiểm tra (07/11/2026)

Đã cài tab chi tiết vào FE, giữ hai tab cũ. BE đã build và đạt 70 kiểm thử (không lỗi), gồm kiểm thử HTTP thật dùng ảnh/box lưu của lượt #49 qua controller có xác thực → YoloClient → AI đang chạy. Database kiểm thử là H2 tạm, không sửa lịch sử MySQL; không upload ảnh lên Cloudinary. Ảnh #49 trả một thân chai thủy tinh; nắp và nhãn chưa phát hiện rõ. Đây là kiểm tra luồng chạy, không phải benchmark độ chính xác. AI đạt 158 kiểm thử; FE đã đạt 44 luồng DOM trước khi cài. Kiểm tra trình duyệt trực tiếp chưa hoàn tất vì công cụ UI không xác định chắc URL hiện tại.

Nguyên nhân lỗi 503 được ghi nhận: BE mặc định gọi cổng 8011 nhưng người dùng chỉ khởi động AI cũ tại 8000. Đã sửa để cả api:app và trashsmart.pipeline.main:app đều cung cấp dịch vụ chi tiết tại /details trong cùng tiến trình AI. Model chi tiết vẫn có trọng số/cấu hình riêng và tải lười, không thay model cũ. Ngưỡng phát hiện bộ phận cho web thử nghiệm tối thiểu 0.5 để loại các đề xuất yếu khi quay ảnh; phần chưa phát hiện được báo rõ trên FE. MaterialThreshold vẫn là 0.7; mọi kết quả thử nghiệm đều cần kiểm tra trực tiếp.

Khởi động AI bình thường, không cần thêm terminal cho 8011:

~~~powershell
cd D:\thacsi\DOAN\HAUI-TRASH\Model_AI\ModelFeatNew\Model_AI_Yolo
python -m uvicorn trashsmart.pipeline.main:app --host 127.0.0.1 --port 8000
~~~

Kiểm tra http://127.0.0.1:8000/details/health. BE mặc định lấy ai.yolo.base-url và nối /details. Nếu chủ động chạy AI chi tiết riêng ở 8011, có thể đặt AI_COMPONENTS_BASE_URL=http://127.0.0.1:8011; không cần cấu hình này cho cách chạy bình thường. DETAILS_RELEASE_PATH tiếp tục chọn phiên bản trọng số thử nghiệm độc lập. BE/start-detailed-stack.ps1 hỗ trợ mở local stack trong nền; không ghi đè FE hoặc model cũ.

Hai checksum model cũ đã kiểm tra lại và không đổi. Bản này vẫn là nghiên cứu, không đánh dấu validated production hoặc endToEndReviewed cho mục đích đánh giá độ chính xác. Nhựa còn yếu trong benchmark crop phụ trợ đã nêu trên.

## Bài báo và dữ liệu tham khảo

1. [SPIN: Hierarchical Segmentation with Subpart Granularity in Natural Images — ECCV 2024](https://joshmyersdean.github.io/spin/index.html), [bài báo](https://arxiv.org/abs/2407.09686). Tham khảo quan hệ vật thể–bộ phận–bộ phận con và giữ vùng con thuộc vật thể cha. Trong taxonomy dùng ở dự án có Bottle-Body-Label và Bottle-Mouth-Cap. SPIN cung cấp hình học bộ phận, không xác nhận bốn vật liệu tái chế.
2. [PartImageNet: A Large, High-Quality Dataset of Parts](https://arxiv.org/abs/2112.00933). Là cơ sở dữ liệu phần–toàn thể mà SPIN mở rộng. Nhãn phần chai Body/Mouth là mức thô hơn nắp/thân/nhãn của bài toán này; không chuyển nhãn Mouth thành vật liệu nắp.
3. [TACO: Trash Annotations in Context for Litter Detection](https://arxiv.org/abs/2003.06975), [repository tác giả](https://github.com/pedropro/TACO). Dùng annotation có tên vật liệu cụ thể để tạo crop phụ trợ. Không coi dataset này là bộ dữ liệu đầy đủ cho phân tích cấu tạo mọi chai. URL nguồn và metadata giấy phép từng ảnh được giữ trong manifest; không tự gán giấy phép MIT của code cho toàn bộ ảnh.

Các công trình trên hỗ trợ từng phần của cách làm. Chưa có bằng chứng từ các nguồn đã kiểm tra rằng chỉ một ảnh RGB luôn xác định đúng vật liệu của tất cả lớp bọc/nút/nắp/nhãn, nhất là khi bị che khuất hoặc có vật liệu nhiều lớp.
