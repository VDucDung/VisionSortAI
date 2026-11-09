# Xuất vùng vật liệu đã duyệt khi chưa gán đủ bộ phận

Không cần đoán nắp để sử dụng vùng thân/nhãn đã kiểm tra. Annotation có `annotationReviewed=true` xác nhận hình học của các khung được liệt kê; `partsExhaustive=false` ghi rõ vẫn thiếu bộ phận nhìn thấy. Chỉ crop có `materialVerified=true` và căn cứ xác nhận mới được xuất cho classifier.

```powershell
python -X utf8 -m trashsmart.components export --data 'D:\thacsi\DOAN\HAUI-TRASH\AI_DATASET\bottle_components' --output 'D:\thacsi\DOAN\HAUI-TRASH\AI_DATASET\bottle_components\04_prepared\reviewed-materials-v3' --include-partial-materials
```

Chọn thư mục output chưa tồn tại. Cờ này không đổi quy tắc detector: chỉ chai `partsExhaustive=true` mới xuất ảnh và nhãn detector. Các khung chưa duyệt, vật liệu chưa xác nhận và sản phẩm trùng giữa các split vẫn bị loại hoặc chặn. Không đặt cờ duyệt chỉ vì có dự đoán của model.

Trong `dataset-report.json`, `manifest` vẫn mô tả crop detector; `materialManifest` lưu từng crop vật liệu, mã nhóm, partType, bbox, checksum ảnh gốc, nguồn/căn cứ xác nhận và việc annotation detector đã đầy đủ hay chưa. Dữ liệu hiện tại dùng vật liệu theo khai báo người dùng, không phải xác minh vật lý độc lập của trợ lý.

Export không huấn luyện hoặc kích hoạt model. Cần đủ lớp vật liệu, kiểm tra nhóm sản phẩm và chia validation/test theo sản phẩm trước khi chạy classifier. Nếu nắp là nút bần hoặc chưa rõ vật liệu, giữ unknown/false trong hợp đồng bốn lớp hiện tại; không đổi thành metal chỉ theo loại chai.
