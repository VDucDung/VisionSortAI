"""Replace the chapter's main comparison with measured YOLO11n Original/Improved ablations."""
import argparse
import copy
import csv
import hashlib
import json
import math
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt

from update_benchmark_chapter import Writer, number, percent, replace_paragraph, text_of


DATASETS = dict(haui="HAUI", taco="TACO v0.2", uavvaste="UAVVaste")
VARIANTS = dict(original="Original", cbam="+ CBAM", eiou="+ EIoU", improved="Improved")
QUALITY = ("precision", "recall", "f1", "map50", "map50_95")


def verify_report(root):
    """Reject incomplete, altered or inconsistent measurements before editing Word."""
    report = json.loads((root / "comparison_original_improved.json").read_text(encoding="utf-8"))
    rows = report["results"]
    expected = {(dataset, variant) for dataset in DATASETS for variant in VARIANTS}
    if len(rows) != 12 or {(r["dataset"], r["variant"]) for r in rows} != expected:
        raise ValueError("All twelve measured ablation rows are required")
    for row in rows:
        if not all(math.isfinite(row[key]) and 0 <= row[key] <= 1 for key in QUALITY):
            raise ValueError("Non-finite or out-of-range quality metric")
        directory = root / row["dataset"] / row["variant"]
        with (directory / "results.csv").open(encoding="utf-8-sig", newline="") as stream:
            if [int(r["epoch"]) for r in csv.DictReader(stream)] != list(range(1, 31)):
                raise ValueError("Incomplete training history")
        with (directory / "weights/best.pt").open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != row["checkpoint_sha256"]:
                raise ValueError("Measured checkpoint changed")
        raw = json.loads((directory / "test_results.json").read_text(encoding="utf-8"))
        if raw["checkpoint_sha256"] != row["checkpoint_sha256"]:
            raise ValueError("Raw evaluation checkpoint differs from the comparison")
        for key in QUALITY:
            measured = raw[key] if key.startswith("map") else raw["fixed_confidence"][key]
            if measured != row[key]:
                raise ValueError("Comparison metric differs from the raw evaluation")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.study.resolve()
    report = verify_report(root)
    rows = report["results"]
    document = Document(args.source)
    start = next(p for p in document.paragraphs if p.style.name == "Heading 2" and p.text.startswith("3.4 "))
    stop = next(p for p in document.paragraphs if p.style.name == "Heading 2" and p.text.startswith("3.5 "))
    node = start._p
    while node is not stop._p:
        following = node.getnext(); node.getparent().remove(node); node = following
    writer = Writer(document, stop._p)
    writer.p("3.4 ĐÁNH GIÁ CẢI TIẾN TRÊN CÙNG MÔ HÌNH YOLO11n", "Heading 2")
    writer.p("3.4.1 Câu hỏi nghiên cứu và đóng góp triển khai", "Heading 3")
    writer.p(
        "Thực nghiệm kiểm tra liệu bổ sung CBAM và thay thành phần CIoU bằng EIoU có cải thiện "
        "khả năng phát hiện rác của YOLO11n trong điều kiện chung hay không. Original là kiến trúc "
        "và loss gốc của YOLO11n được huấn luyện trên dữ liệu đích. Improved là cấu hình kết hợp "
        "hai yếu tố đã định trước. Hai hàng ablation chỉ thêm CBAM hoặc EIoU giúp tách tác động "
        "của từng yếu tố. Tên Improved thể hiện cấu hình đề xuất; mức tăng hoặc giảm được xác định bằng phép đo."
    )
    writer.p(
        "CBAM do Woo và cộng sự công bố tại ECCV 2018 [18]. EIoU được Zhang và cộng sự công bố "
        "trong Neurocomputing năm 2022 [19]. Bài hội nghị ICITRI 2025 [20] có chủ đề tích hợp CBAM "
        "vào YOLO11n cho phát hiện rác. Nghiên cứu này sử dụng phương trình trong hai bài gốc để "
        "triển khai, còn [20] cung cấp bối cảnh liên quan từ tóm tắt của nhà xuất bản. Chưa có đủ "
        "toàn văn [20] để tuyên bố tái hiện chính xác cấu hình của bài đó."
    )
    writer.p(
        "Phần việc của đồ án gồm lựa chọn vị trí tích hợp tại neck, viết mô-đun attention và loss "
        "trong project, bảo toàn khởi tạo của mạng gốc, xây dựng phép ablation và đo trên ba bộ dữ liệu. "
        "CBAM và EIoU được ghi nhận là phương pháp đã công bố; đóng góp ở đây là triển khai và "
        "kiểm chứng sự kết hợp cho bài toán của hệ thống."
    )
    writer.p("3.4.2 Cấu trúc và hàm mất mát được thay đổi", "Heading 3")
    writer.p(
        "CBAM được đặt sau ba khối C3k2 đầu ra P3, P4, P5 của neck, tương ứng tầng 16, 19, 22 "
        "trong bản YOLO11n đã dùng. Attention kênh sử dụng average pooling và max pooling với "
        "MLP dùng chung, tỷ lệ giảm chiều 16. Attention không gian được áp dụng tiếp theo với "
        "convolution 7 × 7 trên hai bản đồ pooling theo kênh. Tensor đầu ra giữ nguyên số kênh và "
        "kích thước không gian, nên giao diện với Detect head được bảo toàn [18]."
    )
    writer.p(
        "Trong nhánh EIoU, chỉ thành phần box regression CIoU được thay bằng phương trình 7 của "
        "[19]: L_EIoU = 1 − IoU + d_tâm²/(c_w² + c_h²) + (w − w_gt)²/c_w² + "
        "(h − h_gt)²/c_h². c_w và c_h là chiều rộng và cao của khung nhỏ nhất bao hai khung; "
        "d_tâm là khoảng cách hai tâm. Cấu hình này sử dụng EIoU, giữ DFL, loss phân lớp và "
        "task-aligned assignment của YOLO11n. Thành phần focal trong phương trình 10 của [19] "
        "không được đưa vào thực nghiệm."
    )
    writer.image(root / "figures/architecture.png", "Hình 3.1 Vị trí CBAM và thay đổi loss trong YOLO11n đề xuất")
    writer.p("3.4.3 Dữ liệu và kiểm soát đối chứng", "Heading 3")
    writer.p(
        "Ba nguồn là HAUI của dự án, TACO v0.2 gồm 715 ảnh và 2.152 annotation [16], và UAVVaste "
        "gồm 772 ảnh và 3.718 annotation [17]. Bốn cấu hình của mỗi nguồn dùng cùng byte ảnh, "
        "nhãn và cách chia. Các loại rác của hai bộ công khai được gộp thành một lớp item. "
        "Phạm vi đối tượng vẫn khác giữa các nguồn, vì vậy kết quả được diễn giải theo từng bộ."
    )
    protocols = {dataset: json.loads((root / dataset / "protocol.json").read_text(encoding="utf-8")) for dataset in DATASETS}
    writer.table("Bảng 3.3 Quy mô các tập dữ liệu dùng chung cho bốn cấu hình",
        ["Dữ liệu", "Ảnh train", "Ảnh validation", "Ảnh test", "Đối tượng test"],
        [(DATASETS[d], *[protocols[d]["counts"][s]["images"] for s in ("train", "valid", "test")],
          protocols[d]["counts"]["test"]["objects"]) for d in DATASETS], [3.2, 2.8, 2.8, 2.8, 2.8])
    writer.p(
        "TACO và UAVVaste được xác minh checksum theo kho phát hành. Ảnh công khai được xử lý "
        "EXIF theo hệ tọa độ COCO và resize giữ toàn khung với cạnh dài tối đa 1.280 pixel. "
        "Khung phát hiện lấy từ hình chữ nhật bao polygon segmentation gốc. Trong gói TACO đã "
        "tải, 2.150/2.152 trường bbox có tọa độ y từ đáy ảnh; chuyển đổi polygon khắc phục sự lệch "
        "hệ tọa độ trước mọi lượt train. source.json giữ cả khung nguồn và khung chuyển đổi."
    )
    writer.p(
        "Hai bộ công khai được chia theo nhóm chụp với tỷ lệ mục tiêu 70/15/15 và seed 42, giữ "
        "mỗi nhóm trong một split. Kiểm tra pixel không phát hiện ảnh trùng hoàn toàn giữa các "
        "split. Các ứng viên dHash của hai bộ đã được xem và là cảnh khác nhau. HAUI giữ cách "
        "chia hiện có với ba cặp cảnh train–validation gần giống. Cả ba tập test đã được đọc trong "
        "đợt đối chiếu kiến trúc trước; đây là giới hạn về lịch sử sử dụng test, không phải holdout mới."
    )
    writer.p("3.4.4 Ngân sách và xác minh khởi tạo", "Heading 3")
    writer.table("Bảng 3.4 Điều kiện huấn luyện và đánh giá chung",
        ["Điều kiện", "Giá trị"], [
        ("Số lượt", "12 lượt mới, 4 cấu hình trên mỗi bộ dữ liệu"),
        ("Khởi tạo", "Cùng YOLO11n COCO pretrained, 80 lớp trước chuyển sang dữ liệu đích"),
        ("Epoch và ảnh", "30 epoch, 640 × 640 pixel, không early stopping"),
        ("Batch và CPU", "Batch 8, 4 thread, workers 0, cache RAM"),
        ("Seed", "42, deterministic bật"),
        ("Optimizer", "AdamW, lr0 0,0005, cosine schedule"),
        ("Augmentation", "Mosaic 0,5, scale 0,3, HSV chung; tắt mosaic 10 epoch cuối"),
        ("Chọn checkpoint", "mAP50–95 validation cao nhất trong cùng 30 epoch"),
        ("P/R/F1", "Confidence 0,25; đối sánh IoU 0,50; NMS IoU 0,70"),
        ("AP", "Confidence 0,001; IoU đánh giá 0,50 đến 0,95; TTA tắt"),
        ], [4.2, 10.2])
    writer.p(
        "Original chỉ kiến trúc và loss nguyên bản; recipe chung trong Bảng 3.4 được công bố "
        "để tách tác động của CBAM và EIoU. Transfer learning áp dụng cho tất cả các hàng. "
        "Mô-đun mới được gắn sau khi nạp trọng số gốc. Kiểm tra hash xác nhận mọi tensor thuộc "
        "mạng gốc có cùng giá trị khởi tạo giữa bốn cấu hình của một bộ; khởi tạo CBAM không "
        "làm đổi luồng RNG toàn cục. Thư viện Ultralytics trên máy được giữ nguyên."
    )
    writer.p("3.4.5 Chất lượng phát hiện trên ba tập test", "Heading 3")
    writer.table("Bảng 3.5 Chỉ số test của mười hai lượt YOLO11n",
        ["Dữ liệu", "Cấu hình", "P (%)", "R (%)", "F1 (%)", "mAP50 (%)", "mAP50–95 (%)"],
        [(DATASETS[r["dataset"]], VARIANTS[r["variant"]], *[percent(r[k]) for k in QUALITY]) for r in rows],
        [2.8, 2.0, 1.8, 1.8, 1.8, 2.05, 2.15])
    writer.image(root / "figures/quality.png", "Hình 3.2 So sánh Original và Improved trên ba bộ dữ liệu")
    writer.p("3.4.6 Phân tích ablation của từng yếu tố", "Heading 3")
    for index, dataset in enumerate(DATASETS, start=6):
        subset = [r for r in rows if r["dataset"] == dataset]
        writer.table(f"Bảng 3.{index} Ablation của YOLO11n trên {DATASETS[dataset]}",
            ["YOLO11n", "CBAM", "EIoU", "Pretrained", "mAP50–95 (%)", "Tham số (triệu)"],
            [(VARIANTS[r["variant"]], "✓" if r["cbam"] else "–", "✓" if r["eiou"] else "–", "✓",
              percent(r["map50_95"]), number(r["parameters"] / 1e6, 3)) for r in subset],
            [2.7, 1.8, 1.5, 2.1, 3.1, 3.2])
        models = {r["variant"]: r for r in subset}
        writer.p(
            f"Trên {DATASETS[dataset]}, thêm riêng CBAM làm mAP50–95 thay đổi "
            f"{number(100 * (models['cbam']['map50_95'] - models['original']['map50_95']))} điểm phần trăm; "
            f"thay riêng EIoU làm thay đổi {number(100 * (models['eiou']['map50_95'] - models['original']['map50_95']))} "
            "điểm phần trăm. Các hàng này tách tác động của từng yếu tố trong cùng recipe. "
            "Chênh lệch của cấu hình kết hợp được giữ nguyên, kể cả khi không cao hơn từng yếu tố riêng."
        )
    writer.table("Bảng 3.9 Chênh lệch Improved so với Original bằng điểm phần trăm",
        ["Dữ liệu", "P", "R", "F1", "mAP50", "mAP50–95"],
        [(DATASETS[item["dataset"]], *[number(item["difference_percentage_points"][k]) for k in QUALITY])
         for item in report["original_vs_improved"]], [3.4, 2.2, 2.2, 2.2, 2.2, 2.2])
    writer.image(root / "figures/training.png", "Hình 3.3 Diễn biến validation và loss của bốn cấu hình")
    writer.p(
        "Giá trị box loss giữa CIoU và EIoU có ý nghĩa và thang đo khác nhau. Đường loss trong "
        "Hình 3.3 dùng để theo dõi diễn biến tối ưu của từng cấu hình; kết luận chất lượng dựa "
        "trên các chỉ số test chung trong Bảng 3.5 và 3.9."
    )
    writer.p("3.4.7 Chi phí và kết quả cùng ảnh đầu vào", "Heading 3")
    writer.table("Bảng 3.10 Quy mô và suy luận CPU của các checkpoint",
        ["Dữ liệu", "Cấu hình", "Tham số (triệu)", "Checkpoint (KiB)", "Suy luận (ms/ảnh)"],
        [(DATASETS[r["dataset"]], VARIANTS[r["variant"]], number(r["parameters"] / 1e6, 3),
          number(r["checkpoint_mb"] * 1e6 / 1024), number(r["inference_ms"])) for r in rows],
        [2.8, 2.2, 2.7, 3.3, 3.4])
    writer.p(
        "Số tham số được đếm trước khi fuse mạng; dung lượng checkpoint là số byte chia 1.024. "
        "Thời gian là số đo suy luận trung bình theo batch trong bước test trên CPU; nó chịu "
        "ảnh hưởng tải máy, trạng thái nguồn điện và khác phạm vi median predict trên một ảnh sau warmup. "
        "evaluation_environment trong từng báo cáo lưu trạng thái nguồn và xung CPU khi đo. EIoU chỉ "
        "thay loss huấn luyện, còn CBAM thêm các lớp suy luận. Các ảnh minh họa được cố định từ "
        "đợt trước và dùng chung cho Original và Improved, không chọn theo kết quả mới."
    )
    for index, dataset in enumerate(DATASETS, start=4):
        writer.image(root / dataset / "sample_prediction/side_by_side.jpg",
                     f"Hình 3.{index} YOLO11n Original và Improved trên cùng ảnh {DATASETS[dataset]}")
    checkpoint_rows = []
    for r in rows:
        run = root / r["dataset"] / r["variant"]
        init = json.loads((run / "initialization.json").read_text())
        history = list(csv.DictReader((run / "results.csv").open(encoding="utf-8-sig")))
        best = max(history, key=lambda item: float(item["metrics/mAP50-95(B)"]))
        checkpoint_rows.append((DATASETS[r["dataset"]], VARIANTS[r["variant"]], init["common_initial_sha256"][:12],
                                len(history), percent(float(best["metrics/mAP50-95(B)"]))))
    writer.table("Bảng 3.11 Kiểm chứng khởi tạo chung và ngân sách huấn luyện",
        ["Dữ liệu", "Cấu hình", "Hash gốc đầu vào", "Epoch hoàn thành", "Val mAP50–95 max (%)"],
        checkpoint_rows, [2.8, 2.2, 4.0, 2.4, 3.0])
    writer.p("3.4.8 Giới hạn và khả năng tái lập", "Heading 3")
    if report.get("execution_interruptions"):
        writer.p(
            "Nhật ký có ghi nhận khoảng gián đoạn dài theo đồng hồ trong lượt huấn luyện. "
            "Hồ sơ execution_interruptions.json lưu lượt bị ảnh hưởng và bằng chứng thời gian. "
            "Thời gian trôi qua của lượt đó bao gồm khoảng gián đoạn, không được xem là thời gian CPU hoạt động liên tục."
        )
    resumed = sorted({r["dataset"] for r in rows if list((root / r["dataset"]).glob("resume_" + r["variant"] + "_*"))})
    if resumed:
        writer.p("Có khôi phục checkpoint tại " + ", ".join(DATASETS[d] for d in resumed) +
                 ". Optimizer và recipe được giữ, phần epoch chưa lưu được chạy lại. Hồ sơ lưu checkpoint "
                 "trước khôi phục. Chuỗi RNG sau khởi động lại có thể khác một lượt chạy liên tục.")
    writer.p(
        "Các chênh lệch là kết quả của một seed, ngân sách hữu hạn và các nhóm chia tập đã nêu. "
        "Lịch sử test đã được công bố; không diễn giải đây là đánh giá trên dữ liệu mới chưa từng "
        "quan sát. Đợt ablation này kiểm chứng hai yếu tố trong một cấu hình đặt trước, chưa đủ "
        "khẳng định tối ưu toàn cục hay ý nghĩa thống kê. Accuracy phân loại vật liệu và mAP "
        "phát hiện là các đại lượng riêng. Confidence của một khung không thay thế độ chính xác tập dữ liệu."
    )
    replace_paragraph(document, "Chương này cập nhật thực nghiệm theo mã nguồn VisionSortAI",
        "Chương này đánh giá hệ thống VisionSortAI và kiểm chứng hai cải tiến CBAM, EIoU trên "
        "cùng mô hình YOLO11n. Đối chứng Original, hai ablation và Improved dùng chung dữ liệu "
        "và ngân sách trên HAUI, TACO, UAVVaste. Kết quả được trình bày theo số đo thực nghiệm.")
    replace_paragraph(document, "Các nhật ký YOLO lịch sử lưu cấu hình",
        "Đợt đối chứng Original–Improved dùng 30 epoch, ảnh 640 pixel và cùng ngân sách cho "
        "bốn cấu hình trên mỗi bộ dữ liệu. Cấu trúc mạng, loss, khởi tạo và giao thức được mô tả "
        "tại mục 3.4. Đo độ trễ FE–BE–AI và tải đồng thời cần công bố thêm điều kiện mạng cùng số yêu cầu xử lý.")
    for node in document.element.body.xpath(".//w:t"):
        if node.text and "So sánh YOLO11n–YOLOv8n" in node.text:
            node.text = node.text.replace("So sánh YOLO11n–YOLOv8n", "So sánh YOLO11n Original–Improved")
    for table in document.tables:
        for row in table.rows:
            if row.cells[0].text == "Mô hình phát hiện chai" and len(row.cells) == 3:
                row.cells[1].text = "Giao thức khóa dữ liệu, 12 lượt train và báo cáo test của bốn cấu hình YOLO11n"
                row.cells[2].text = "Đối chiếu Original, từng yếu tố CBAM/EIoU và Improved trong cùng điều kiện"
    discussion = next(p for p in document.paragraphs if p.style.name == "Heading 2" and p.text.startswith("3.11 "))
    ending = next(p for p in document.paragraphs if p.style.name == "Heading 1" and p.text.startswith("KẾT LUẬN VÀ KHUYẾN NGHỊ"))
    node = discussion._p.getnext()
    while node is not ending._p:
        following = node.getnext(); node.getparent().remove(node); node = following
    summary = Writer(document, ending._p)
    wins = sum(item["difference_percentage_points"]["map50_95"] > 0 for item in report["original_vs_improved"])
    summary.p(f"Trong phép đối chứng cùng YOLO11n với 30 epoch ở 640 pixel, cấu hình CBAM+EIoU "
              f"có mAP50–95 cao hơn Original trên {wins}/3 bộ dữ liệu. Bảng 3.5 và 3.9 giữ đầy đủ "
              "các chỉ số tăng hoặc giảm. Các hàng chỉ thêm CBAM hoặc EIoU giúp xác định tác động "
              "của từng yếu tố. Những kết quả này cho phép đánh giá phần cải tiến đã triển khai trên cùng mô hình nền.")
    summary.p("Đóng góp thực nghiệm là tích hợp hai kỹ thuật có nguồn, kiểm tra khởi tạo công bằng, "
              "đánh giá trên ba nguồn ảnh và cung cấp công cụ chạy độc lập Original/Improved. "
              "Kết luận gắn với một seed, lịch sử dùng test và ngân sách đã công bố; chưa thay thế "
              "đánh giá end-to-end của nhận diện, phân loại vật liệu và hướng dẫn xử lý.")
    appendix_heading = next(p for p in document.paragraphs if p.style.name == "Heading 1" and p.text.startswith("PHỤ LỤC HỒ SƠ"))
    references = Writer(document, appendix_heading._p)
    references.p("[18] Woo, S., Park, J., Lee, J.-Y. và Kweon, I. S. (2018), CBAM Convolutional Block Attention Module, ECCV, tr. 3–19. DOI: 10.1007/978-3-030-01234-2_1.")
    references.p("[19] Zhang, Y.-F. và cộng sự (2022), Focal and efficient IoU loss for accurate bounding box regression, Neurocomputing 506, tr. 146–157. DOI: 10.1016/j.neucom.2022.07.042.")
    references.p("[20] CBAM-Enhanced YOLO11n A Lightweight and Efficient Model for Solid Waste Detection Compared to YOLOv9n YOLOv10n and RT-DETR (2025), ICITRI. DOI: 10.1109/ICITRI67507.2025.11232874. Tham khảo tóm tắt của nhà xuất bản.")
    appendix = Writer(document, document.element.body.sectPr)
    appendix.p("A.8 HỒ SƠ YOLO11n ORIGINAL VÀ IMPROVED", "Heading 2")
    appendix.p("Hồ sơ tại outputs/yolo11-original-improved-20261116 trong ModelAI. study_plan.json "
               "lưu thiết kế; initialization.json xác minh tensor gốc chung; comparison_original_improved.json "
               "và CSV lưu đủ 12 hàng số đo. Mỗi bộ có bốn thư mục original, cbam, eiou, improved. "
               "Hướng dẫn ORIGINAL_IMPROVED.md mô tả phương pháp, nguồn và lệnh train/evaluate/predict độc lập.")
    for r in rows:
        paragraph = appendix.p(f"{DATASETS[r['dataset']]} {VARIANTS[r['variant']]} SHA-256\n{r['checkpoint_sha256']}")
        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        paragraph.paragraph_format.first_line_indent = Pt(0)
        paragraph.paragraph_format.space_after = Pt(4)
        paragraph.paragraph_format.line_spacing = 1.1
        for run in paragraph.runs: run.font.size = Pt(12)
    args.output.mkdir(parents=True, exist_ok=True)
    # Small ablation/delta tables should not split across consecutive pages.
    for table in document.tables:
        labels = [cell.text for cell in table.rows[0].cells]
        if labels[:3] == ["YOLO11n", "CBAM", "EIoU"] or labels == ["Dữ liệu", "P", "R", "F1", "mAP50", "mAP50–95"]:
            for index, row in enumerate(table.rows):
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        paragraph.paragraph_format.keep_with_next = index < len(table.rows) - 1
    full = args.output / "De_an_Vu_Duc_Dung_YOLO11n_Original_Improved.docx"
    document.save(full)
    chapter = Document(full)
    nodes = list(chapter.element.body)
    start = next(i for i, node in enumerate(nodes) if node.tag == qn("w:p") and text_of(node).startswith("CHƯƠNG 3 ") and i > 200)
    end = next(i for i in range(start + 1, len(nodes)) if nodes[i].tag == qn("w:p") and text_of(nodes[i]).startswith("KẾT LUẬN VÀ KHUYẾN NGHỊ"))
    section = copy.deepcopy(chapter.element.body.sectPr)
    for node in list(chapter.element.body): chapter.element.body.remove(node)
    for node in nodes[start:end]: chapter.element.body.append(node)
    chapter.element.body.append(section)
    chapter.save(args.output / "Chuong_3_YOLO11n_Original_Improved.docx")
    print(full)


if __name__ == "__main__":
    main()
