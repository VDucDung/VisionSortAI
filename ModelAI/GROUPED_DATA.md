# Ảnh chia theo thư mục vật liệu

Reader hỗ trợ các thư mục con trong `01_user_photos`: `images`, `glass`, `metal`, `paper`, `plastic`, `needs_review` (kể cả các thư mục lồng bên trong). Không cần chuyển ảnh về `images`. `evidence` là ảnh chứng cứ, không tự đưa vào danh sách ảnh huấn luyện.

## CSV nối với ảnh như thế nào

- Giữ nguyên 10 cột hiện tại. Trường `image_path=glass/ten_anh.jpg` trong `notes` tính từ `01_user_photos`; cũng nhận đường dẫn đầy đủ từ dataset như `01_user_photos/glass/ten_anh.jpg`.
- `image_path` được ưu tiên. `image=ten_anh.jpg` chỉ dùng khi tên đó duy nhất, hoặc có `folder=glass`. Tên trùng ở nhiều thư mục cần `image_path` rõ ràng.
- Nếu một dòng mô tả nhiều góc cùng chai, có thể dùng `group_id=bottle_001` và tên ảnh `bottle_001_front.jpg`, `bottle_001_back.jpg`, `bottle_001_side2.jpg`…
- Tool dùng mã nhóm CSV, không lấy tên file dài của dataset làm mã nhóm mới. Nhiều ảnh cùng sản phẩm nên chung group sau khi rà soát.
- `source_split=train/valid/test` được giữ; `valid` chuẩn hóa thành `val`. Prefix `train__`, `valid__`, `test__` cũng được kiểm tra. Không tự chia lại các ảnh này theo hash nhóm.
- Chỉ các giá trị `verified=true` kèm vật liệu biết rõ và bằng chứng mới được coi là xác nhận. Tên thư mục và nhãn YOLO không tự xác minh vật liệu nắp/thân/nhãn.
- Ảnh ghi `object_type=can` hoặc `exclude_from_bottle_training=true` chỉ xem làm mẫu; không được lưu/xuất như chai. Ảnh chưa rõ loại vật thể vẫn cần người rà soát chọn đúng chai.

## Kiểm kê và ảnh trùng

```powershell
$dataset='D:\thacsi\DOAN\HAUI-TRASH\AI_DATASET\bottle_components'
python -X utf8 -m trashsmart.components audit-intake --data $dataset --hash-images --output (Join-Path $dataset 'intake-audit.json')
```

Báo cáo ghi số ảnh theo thư mục, đường dẫn thiếu/thừa, xung đột CSV, group đi qua nhiều split và ảnh trùng SHA256. SHA256 chỉ phát hiện file trùng chính xác, chưa phát hiện ảnh chụp gần giống hoặc bản đã nén lại.

Kiểm kê ngày 03/11/2026: 5.935 ảnh khớp 5.935 dòng CSV; không thiếu file; 216 ảnh needs_review; 129 nhóm trùng file, 45 nhóm có bản trùng giữa các split. Dữ liệu mới có 5.934 dòng `body_verified=false`, tất cả nắp/nhãn chưa xác minh. Dòng đã xác nhận thân duy nhất là lon mẫu `can_001`, được loại khỏi phạm vi chai.

Các nhóm trùng cần được xử lý trước đánh giá model. Export đã chặn ảnh trùng trong tập được chọn. Không sửa ảnh/CSV hoặc di chuyển file chỉ vì audit phát hiện trùng.

## Khung chai gợi ý

```powershell
python -X utf8 -u -m trashsmart.components propose-bottles --data $dataset --weights '.\yolo11n.pt' --output (Join-Path $dataset '02_annotations\user-bottle-proposals-v2.jsonl') --batch 4 --imgsz 512 --threads 4
```

Dùng checkpoint COCO có sẵn trên máy, chỉ chọn lớp `bottle`, chạy offline. Không dùng detector bốn vật liệu cũ để khẳng định mọi vật thể là chai. Mỗi nhóm ảnh trùng chính xác chỉ quét một bản, ưu tiên test rồi val rồi train; các bản còn lại được ghi alias trong report. CSV/split gốc không đổi.

Đầu ra là khung chai **gợi ý chưa duyệt**, chưa có khung nắp/thân/nhãn hoặc vật liệu. Ảnh không có dự đoán vẫn ở diện cần rà soát, không bị kết luận là không có chai. Chất lượng phụ thuộc model COCO; khung gợi ý cần kiểm tra lại trên ảnh.

Nếu output trong `02_annotations`, khi hoàn tất job sẽ cập nhật `proposals.active.json` để tool đọc phiên bản mới. Không ghi đè proposal cũ; chọn tên phiên bản mới. Annotation đã được người duyệt trong `annotations.jsonl` luôn được ưu tiên.

```powershell
python -m trashsmart.components annotate --data $dataset
```

Mở `http://127.0.0.1:8766`. Tool đọc tất cả các thư mục mới, hiển thị dòng CSV đúng ảnh và nguyên split nguồn. Khi có khung gợi ý, kiểm tra/sửa khung chai rồi thêm từng bộ phận nhìn thấy. Các phần chưa biết vật liệu giữ `unknown,false`. Nhấn “đã gán đủ” chỉ khi thực sự đủ các bộ phận nhìn thấy. Chuyển ảnh hoặc chuyển loại bộ phận sẽ xóa xác nhận vật liệu còn giữ từ lựa chọn trước để tránh áp nhầm.

Không tự đưa các proposal vào master annotation hoặc huấn luyện. Sau khi duyệt xong mới export sang một thư mục `04_prepared` mới theo `COMPONENTS.md`. Với model vật liệu bộ phận, vẫn cần ảnh cắt có vật liệu đã xác minh; dữ liệu phân loại toàn vật thể không thay thế nhãn bộ phận.
