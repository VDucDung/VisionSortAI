# Nhận diện bộ phận chai — đồ án/nghiên cứu

Đã bổ sung code dữ liệu, huấn luyện CPU/Colab, inference có kiểm soát, và hợp đồng tích hợp BE/FE. **Chưa có checkpoint bộ phận đã được đánh giá và bật trong ứng dụng.**

## 1. Bổ sung ảnh và xác minh vật liệu

Đọc `D:\thacsi\DOAN\HAUI-TRASH\AI_DATASET\bottle_components\README.md`.
Ảnh đặt trong `01_user_photos/images`; cách điền vật liệu xem `examples/materials.example.csv`.

Trong thư mục `ModelAI`, với Python đang cài dependencies của project:

```powershell
$dataset='D:\thacsi\DOAN\HAUI-TRASH\AI_DATASET\bottle_components'
python -m trashsmart.components inventory --data $dataset
python -m trashsmart.components annotate --data $dataset
```

Mở `http://127.0.0.1:8766`. Mỗi ảnh cần khung chai và các khung bộ phận nhìn thấy. Body là thân/vỏ từ cổ xuống đáy, có thể chồng nhãn. Không vẽ phần bị che khuất. Xác nhận đã gán đủ mỗi chai để không biến bộ phận bỏ sót thành background. Vật liệu phải có `materialVerified=true` và `verificationBasis` mới được đưa vào classifier.

## 2. Dữ liệu công khai

```powershell
python -m trashsmart.components fetch-public --data $dataset --limit 483
python -m trashsmart.components import-spin --data $dataset
```

Tải chọn lọc ảnh gốc bằng HTTP Range, không tải toàn bộ archive PartImageNet. Không lấy mask PNG hoặc file `__MACOSX` làm ảnh. Metadata SPIN gồm 483 ảnh chai có subpart: 409 train, 24 val, 50 test; 227 annotation nắp, 343 annotation nhãn. Số annotation không bằng số chai có bộ phận. Nguồn: SPIN `spin_coco.zip`, PartImageNet Seg; URL và SHA256 được lưu trong `03_public/source-report.json`.

Nguồn hình học không có ground truth bốn vật liệu. Annotation chuyển đổi được để `annotationReviewed=false`, `partsExhaustive=false`, material `unknown`. Cần rà soát mapping, thiếu bộ phận, nhóm sản phẩm trước khi export. Một ảnh SPIN có thể chỉ chú thích một đối tượng chính dù có nhiều chai trong ảnh; bộ chuyển đổi chỉ nhận một whole + một body, bỏ qua trường hợp mơ hồ. Với public data, mã ảnh chưa đảm bảo hai ảnh khác nhau không cùng sản phẩm; gộp group khi rà soát. Giữ bộ ảnh thật độc lập để đánh giá cuối cùng.

Thông tin sử dụng và trích dẫn SPIN: `03_public/spin_metadata/datasheet.md`; điều kiện ảnh ImageNet/PartImageNet vẫn áp dụng riêng. Đây là pipeline nghiên cứu, không khẳng định đủ điều kiện thương mại cho mọi ảnh.

## 3. Export dữ liệu đã rà soát

```powershell
$prepared=Join-Path $dataset '04_prepared\v1'
python -m trashsmart.components export --data $dataset --output $prepared
```

Không ghi đè export cũ. Cùng group phải ở cùng split; ảnh trùng bị chặn; ảnh minh họa bị chặn. Detector học trên crop chai có đủ annotation. Classifier chỉ nhận crop vật liệu đã kiểm chứng. `dataset-report.json` ghi nguồn ảnh, group, split, SHA256 và số lượng theo lớp.

## 4. Huấn luyện CPU trên máy này

Đã có dataset detector-only `AI_DATASET/bottle_components/04_prepared/public-detector-v1`, gồm 475 crop chai từ annotation SPIN đã công bố. Tập này được chấp nhận cho baseline nghiên cứu dựa trên nhãn tác giả và kiểm tra hình học tự động, không phải tuyên bố đã rà soát thủ công mới từng ảnh. Xem `source-acceptance.json` và `accepted-source-annotations.jsonl` trong export. Master annotation vẫn chờ rà soát, toàn bộ vật liệu vẫn chưa được xác minh.

Pilot thật một epoch, YOLO11n, ảnh 416, batch 2, CPU 4 thread trên 402 crop train đã hoàn tất; `results.csv` ghi khoảng 126,6 giây cho epoch đầu. Đường dẫn candidate: `05_models/public-detector-pilot-v1/detector/weights/best.pt`. Đây chỉ là điểm xuất phát; khả năng tìm nắp/nhãn còn yếu và chưa bật trong app. Không dùng thời gian này làm cam kết cho mọi cấu hình/số epoch.

CPU chạy được; máy kiểm tra không có CUDA. Đã đo riêng ResNet18 khoảng 32 ms/crop 224×224, batch=1, 4 thread, 5 lần sau warmup. Đây là thời gian forward của mạng chưa huấn luyện, không phải thời gian train hay benchmark toàn pipeline. Không thể suy ra số giờ train chỉ từ phép đo này.

Chạy pilot trước, rồi tăng epoch sau khi có thời gian mỗi epoch:

```powershell
python -u -m trashsmart.components train-detector --data $prepared --output (Join-Path $dataset '05_models\cpu-detector-v1') --device cpu --epochs 5 --batch 2 --imgsz 416 --workers 0 --threads 4
python -u -m trashsmart.components train-material --data $prepared --output (Join-Path $dataset '05_models\cpu-material-v1') --device cpu --epochs 20 --batch 4 --workers 0 --threads 4
```

Nếu PowerShell cho phép chạy script local, có thể dùng wrapper `train-components-cpu.ps1`; các lệnh Python trực tiếp ở trên không phụ thuộc execution policy của file `.ps1`.

Để chạy nghiên cứu detector lâu hơn sau pilot, dùng dataset công khai đã chuẩn bị và output mới (40 epoch là cấu hình thử, không đảm bảo đạt chất lượng):

```powershell
python -u -m trashsmart.components train-detector --data (Join-Path $dataset '04_prepared\public-detector-v1') --output (Join-Path $dataset '05_models\public-detector-40epochs') --device cpu --epochs 40 --batch 2 --imgsz 416 --workers 0 --threads 4
```

Job một epoch đã hoàn tất không dùng `--resume` như job bị gián đoạn. Muốn khởi tạo job mới từ checkpoint pilot, thêm `--weights` trỏ tới `best.pt` của pilot. Kiểm tra dữ liệu và kết quả validation trước khi tiếp tục tối ưu, không điều chỉnh theo test rồi báo test là độc lập.

Script chạy foreground, hiển thị log, lưu checkpoint riêng; không tự thay power/sleep settings của Windows. Giữ máy cắm điện và cho phép ứng dụng tiếp tục chạy. Không đảm bảo hoàn thành trong một đêm. Detector khởi tạo từ YOLO11n pretrained; material baseline ResNet18 pretrained, freeze backbone, train lớp cuối với transform resize toàn crop giống inference. Pretrained weights sẽ tải lần đầu; không ghi đè checkpoint hiện tại của app.

Tiếp tục material bằng `--resume path/to/last.pth` và `--epochs` là tổng epoch mong muốn. Detector dùng resume chuẩn Ultralytics từ `last.pt`; cấu hình job cũ được phục hồi. Các lệnh không tự nâng model vào production.

## 5. Colab GPU miễn phí

```powershell
python -m trashsmart.components package-training --data $prepared --output (Join-Path $dataset 'training-v1.zip')
```

Mở `notebooks/bottle_components_colab.ipynb` trong Colab, chọn GPU và upload bundle được tạo. Bundle chỉ chứa code huấn luyện cùng crop/nhãn đã export; không có `.env`, tài khoản hay lịch sử. Người dùng tự thực hiện upload bằng tài khoản của mình. Notebook ghi candidate riêng; tải về kết quả trước khi Colab thu hồi phiên. Hạn mức GPU phụ thuộc tài khoản/dịch vụ.

## 6. Đánh giá và bật inference

```powershell
python -m trashsmart.components evaluate --data $prepared --output (Join-Path $dataset '05_models\evaluation-v1') --weights 'PATH_TO_PARTS_BEST_PT' --resume 'PATH_TO_MATERIAL_BEST_PTH' --device cpu
```

Report có detector metrics, confusion matrix/macro F1 vật liệu và SHA256. Sau đó phải kiểm tra end-to-end trên ảnh thật: tìm đủ bộ phận, đúng chai cha, khung hợp lệ, nhãn giấy/nhựa không bị đoán mặc định. Chọn ngưỡng từ validation; không điều chỉnh theo test rồi báo test như độc lập. Nếu chưa đạt, bổ sung dữ liệu và train lại.

Chỉ sau khi rà soát kết quả, copy hai checkpoint vào `trashsmart/models/components`, tạo `release.json` theo `release.example.json`, điền SHA256 và đường dẫn report, xác nhận `validated=true`. Report cần `split=test`, `endToEndReviewed=true` và checksum trùng checkpoint. `endToEndReviewed` chỉ đổi sau khi kiểm tra thực tế, không tự đánh dấu bằng script. Bật `PARTS_ENABLED=true`, cấu hình `PARTS_RELEASE_PATH` và khởi động lại AI.

`GET /metadata` và `/health` trả capability bộ phận riêng với model chai. Model thiếu/chưa được xác nhận: `MODEL_UNAVAILABLE`, không trả dự đoán giả. Mặc định `NOT_RUN`. Lỗi inference: `FAILED`, vẫn giữ kết quả nhận diện chai. `COMPLETED` kèm mảng rỗng nghĩa là đã chạy nhưng không tìm thấy bộ phận đủ điều kiện.

BE/FE nhận thêm `componentCount`, `componentModelVersion`, `detections[].componentAnalysisStatus`, `detections[].components[]`; count cũ vẫn là số chai. Hai confidence của bộ phận là điểm model, không phải xác suất đã được hiệu chỉnh. Lịch sử cũ không được tự bổ sung vật liệu bộ phận. Quét ảnh mới sau khi bật model để có kết quả mới; retry lượt DONE giữ nguyên dữ liệu lịch sử.
