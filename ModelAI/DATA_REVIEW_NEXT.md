# Trạng thái và bước bổ sung dữ liệu

Đợt CPU `research-detector-v2` đã hoàn tất 40 epoch. Đây là detector **vị trí** nắp/thân/nhãn. Chưa có classifier vật liệu từng bộ phận được huấn luyện và chưa kích hoạt model mới trên website.

## Kết quả hiện có

- Test công khai: 49 ảnh crop chai, 111 bộ phận; mAP50 = 0.6888 và mAP50–95 = 0.5016. Không diễn giải thành “68,9% chính xác vật liệu”.
- 1.271 ảnh ứng viên, 4.825 khung bộ phận gợi ý sau khi áp dụng rà soát phạm vi; đều chưa phải nhãn chuẩn.
- Đã xem 14 ảnh có đề xuất bộ phận. Lỗi gồm bỏ sót nắp/nhãn chai nằm ngang, trùng khung nhãn, nhầm miệng chai thành nắp và khung cha chứa nhiều nền/không bao đủ chai.
- 3 ảnh gốc được xem riêng và sửa nhãn hình học: `plastic_00235`, `plastic_01198`, `plastic_01091`. Tổng 4 chai / 11 bộ phận. Vật liệu vẫn `unknown`.
- `04_prepared/reviewed-user-geometry-v1` chỉ có 4 crop **train**; chưa dùng để đánh giá hay huấn luyện một bản phát hành mới. Cần tiếp tục rà soát ảnh và 83 cặp gần giống trước khi gộp dữ liệu.

Hồ sơ và ảnh đối chiếu ở `AI_DATASET/bottle_components/02_annotations/component-review-v2/`. Master trước khi thêm 3 ảnh có bản sao lưu trong thư mục này.

## Phần người dùng cần bổ sung

Dữ liệu hiện tại chủ yếu là ảnh từ bộ dữ liệu cũ. Nhãn “glass/plastic/metal/paper” ở thư mục là nhãn vật thể tổng thể, không chứng minh được vật liệu nắp và nhãn. Để huấn luyện classifier vật liệu, cần chai bạn kiểm tra trực tiếp hoặc tài liệu nhà sản xuất xác nhận đúng mẫu và đúng bộ phận.

1. Đợt đầu chuẩn bị 20–30 mẫu chai khác nhau, gồm chai thủy tinh, chai nhựa và chai kim loại nếu có. Giấy thường là **nhãn chai**, không cần tìm “chai giấy”. Ghi lại cả mẫu có nhãn nhựa, chai không nhãn, nắp nhựa/kim loại nếu có.
2. Mỗi mẫu chụp 3–5 ảnh: toàn chai phía trước, phía sau, bên hông hoặc nằm ngang, cận nắp và cận nhãn. Ảnh rõ, đủ sáng, thấy trọn chai, xen kẽ nền sáng/tối. Không cần tự khoanh vùng.
3. Đặt vào `01_user_photos/images/` hoặc thư mục vật liệu bạn đang dùng. Tên ví dụ `bottle_real_001_front.jpg`, `bottle_real_001_back.jpg`, `bottle_real_001_side.jpg`. Chấp nhận JPG, PNG, WEBP. Không dùng ảnh tổng hợp để thay bằng chứng thật.
4. Trong `materials.csv`, một dòng cho `group_id=bottle_real_001` có thể khớp các góc trên bằng tên. Để `notes` có `object_type=bottle` và **không thêm image_path cho riêng một góc** khi muốn khớp cả nhóm. Ảnh cùng mẫu sản phẩm phải dùng chung mã nhóm; không chia các góc vào nhiều split.
5. Điền riêng `body_material`, `cap_material`, `label_material`; chỉ dùng `glass`, `metal`, `paper`, `plastic`, `unknown`. Các cờ `_verified` chỉ là `true` khi đã kiểm chứng phần tương ứng. `verification_basis` ghi rõ phần nào kiểm chứng bằng cách nào. Chưa chắc thì giữ `unknown/false`. Không có nhãn không đồng nghĩa có nhãn giấy.
6. Ảnh tháo nắp/nhãn và tài liệu đối chiếu đặt trong `01_user_photos/evidence/bottle_real_001/`, dẫn đường dẫn vào ghi chú/bằng chứng. Thư mục evidence không được đưa tự động vào train.

Giữ một số mẫu sản phẩm riêng cho test; sau khi nhận ảnh mình sẽ kiểm tra nhóm/trùng, chia tập và khoanh vùng. Số lượng trên là đợt khởi đầu, chưa đủ để hứa hẹn độ chính xác; phần thiếu sẽ xác định từ kiểm kê lớp và kết quả validation.

## Công cụ rà soát cục bộ

Trong PowerShell tại thư mục `ModelAI` của project:

```powershell
python -X utf8 -m trashsmart.components annotate --data 'D:\thacsi\DOAN\HAUI-TRASH\AI_DATASET\bottle_components' --port 8766
```

Mở `http://127.0.0.1:8766/`. Công cụ đọc đề xuất mới, ưu tiên annotation đã duyệt trong master, chỉ lưu trên máy. Có thể xem mẫu đã sửa bằng cách chọn `plastic_00235`, `plastic_01198` hoặc `plastic_01091` theo tên ảnh. Việc chọn vật liệu/đánh dấu verified trên công cụ phải dựa vào bằng chứng, không dựa riêng hình dáng.

Sau khi đủ dữ liệu: xuất crop đã duyệt → train detector và classifier vật liệu → đánh giá từng lớp và tình huống bỏ sót/ghép nhầm chai → kiểm tra FE/BE/AI trên ảnh thật → mới tạo bản phát hành model. Thời gian chạy CPU không thể thay thế nhãn vật liệu được kiểm chứng.
