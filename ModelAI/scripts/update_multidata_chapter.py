"""Add the completed three-dataset experiment to the previously reviewed thesis."""

import argparse
import copy
import csv
import hashlib
import json
import math
import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from update_benchmark_chapter import Writer, number, percent, replace_paragraph, text_of


DATASET_NAMES = {"haui": "HAUI", "taco": "TACO v0.2", "uavvaste": "UAVVaste"}
MODEL_NAMES = {"yolo11n": "YOLO11n", "yolov8n": "YOLOv8n"}
QUALITY_METRICS = ("precision", "recall", "f1", "map50", "map50_95")


def verify_results(root):
    report = json.loads((root / "comparison_three_datasets.json").read_text(encoding="utf-8"))
    plan = report["study_plan"]
    if set(plan["datasets"]) != set(DATASET_NAMES) or len(report["results"]) != 6:
        raise ValueError("Complete measured results for all six model/dataset pairs are required")
    expected_pairs = {(dataset, model) for dataset in DATASET_NAMES for model in MODEL_NAMES}
    if {(row["dataset"], row["model"]) for row in report["results"]} != expected_pairs:
        raise ValueError("Missing or repeated model/dataset pairs")
    for row in report["results"]:
        if not all(math.isfinite(row[key]) and 0 <= row[key] <= 1 for key in QUALITY_METRICS):
            raise ValueError("Invalid measured quality metrics")
        with Path(row["checkpoint"]).open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != row["checkpoint_sha256"]:
                raise ValueError("Evaluated checkpoint changed")
        directory = root / row["dataset"] / row["model"]
        with (directory / "results.csv").open(encoding="utf-8-sig", newline="") as stream:
            epochs = [int(record["epoch"]) for record in csv.DictReader(stream)]
        if epochs != list(range(1, plan["epochs"] + 1)):
            raise ValueError("Training is incomplete")
    for dataset in DATASET_NAMES:
        if not (root / dataset / "sample_prediction/side_by_side.jpg").is_file():
            raise FileNotFoundError(f"Generate the preselected same-image comparison for {dataset}")
    return report


def renumber_previous_content(document):
    pattern = re.compile(r"Bảng 3\.(8|9|10|11|12)(?!\d)")
    for node in document.element.body.xpath(".//w:t"):
        text = node.text or ""
        node.text = pattern.sub(lambda match: "Bảng 3." + str(int(match[1]) + 4), text)
        node.text = node.text.replace("Hình 3.3", "Hình 3.7")


def subheading(writer, text):
    paragraph = writer.p(text, "Heading 4")
    for run in paragraph.runs:
        run.font.name = "Times New Roman"
        run.font.size = Pt(14)
        run.font.color.rgb = RGBColor(0, 0, 0)
        run.bold = True
    return paragraph


def delta(value):
    return ("+" if value > 0 else "") + number(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.study.resolve()
    report = verify_results(root)
    plan = report["study_plan"]
    rows = report["results"]
    by_dataset = {
        dataset: {row["model"]: row for row in rows if row["dataset"] == dataset}
        for dataset in DATASET_NAMES
    }
    document = Document(args.source)
    # The expanded caption index otherwise leaves one entry on a separate page.
    index_style = document.styles["toc 1"].paragraph_format
    index_style.space_before = Pt(0)
    index_style.space_after = Pt(4)
    index_style.line_spacing = 1.15
    if any(p.text.startswith("3.4.7 ") for p in document.paragraphs):
        raise ValueError("Use the reviewed thesis before the three-dataset update as the source")
    renumber_previous_content(document)
    for paragraph in document.paragraphs:
        if paragraph.text.startswith("Các nhật ký YOLO lịch sử lưu cấu hình"):
            paragraph.text = paragraph.text.replace("Đợt đối chứng mới dùng", "Đợt đối chứng ban đầu dùng")
        elif paragraph.text.startswith("Đợt chạy sử dụng ngân sách 20 epoch"):
            paragraph.text = paragraph.text.replace("Kết quả trong chương gắn", "Các kết quả tại mục 3.4.3 đến 3.4.6 gắn")
    replace_paragraph(
        document, "Đợt đối chứng bổ sung sử dụng cùng dữ liệu, 20 epoch",
        "Ở đợt đối chứng ban đầu với 20 epoch và 416 pixel, YOLO11n cao hơn 0,073 điểm "
        "phần trăm mAP50–95, còn YOLOv8n cao hơn về F1 tại confidence 0,25. Đợt mở rộng "
        "cho thấy thứ hạng thay đổi theo dữ liệu và tiêu chí; cấu hình đã thử chưa chứng minh "
        "YOLO11n vượt trội toàn diện.",
    )
    replace_paragraph(
        document, "Phạm vi thực nghiệm gồm lớp phát hiện item",
        "Các phép đối chứng dùng một seed và ngân sách 20 hoặc 30 epoch đã công bố. "
        "Tập test HAUI đã xuất hiện trong đánh giá trước và lượt YOLOv8n có khôi phục checkpoint. "
        "TACO và UAVVaste được chia theo nhóm chụp; số nhóm hữu hạn giới hạn khả năng khái quát. "
        "Đánh giá toàn hệ thống cần thêm bằng chứng về giao diện, phân quyền, độ trễ và chất lượng gợi ý.",
    )
    stop = next(p for p in document.paragraphs if p.style.name == "Heading 2" and p.text.startswith("3.5 "))
    writer = Writer(document, stop._p)
    writer.p("3.4.7 Thực nghiệm mở rộng trên ba bộ dữ liệu", "Heading 3")
    writer.p(
        "Đợt mở rộng đánh giá YOLO11n và YOLOv8n trên HAUI, TACO v0.2 và UAVVaste. "
        "Mỗi bộ dữ liệu có một cặp mô hình được huấn luyện riêng từ trọng số COCO pretrained. "
        "Hai kiến trúc dùng cùng dữ liệu, ngân sách và quy tắc chọn checkpoint trong từng cặp. "
        "Mức cải thiện được xác định từ kết quả test của từng bộ."
    )
    subheading(writer, "3.4.7.1 Dữ liệu và quy tắc chuyển đổi nhãn")
    writer.p(
        "HAUI dùng bản dữ liệu đã khóa của dự án. TACO v0.2 từ kho Zenodo có 715 ảnh và "
        "2.152 đối tượng có segmentation, thuộc 60 loại rác. UAVVaste có 772 ảnh và 3.718 "
        "annotation rác. Các loại rác gốc trong hai bộ công khai được gộp thành một lớp item. "
        "Phạm vi đối tượng theo nhãn của từng nguồn được giữ rõ khi diễn giải các kết quả [16], [17]."
    )
    writer.p(
        "Các gói công khai được xác minh MD5 theo kho phát hành. Chiều ảnh được chuẩn hóa "
        "theo EXIF cho khớp hệ tọa độ COCO, sau đó resize giữ toàn khung với cạnh dài tối đa "
        "1.280 pixel. Khung phát hiện là hình chữ nhật bao quanh polygon segmentation gốc. "
        "Trong bản TACO v0.2 đã tải, 2.150 trong 2.152 trường bbox dùng tọa độ y từ đáy ảnh, "
        "còn polygon khớp hệ tọa độ ảnh từ trên xuống. Chuyển đổi từ polygon được thực hiện "
        "trước huấn luyện cho cả hai kiến trúc. source.json lưu khung gốc và khung chuyển đổi."
    )
    writer.p(
        "TACO được chia theo nhóm batch và UAVVaste theo tiền tố phiên chụp, với tỷ lệ mục tiêu "
        "70/15/15 và seed 42. Mỗi nhóm nằm trong một split. Số ảnh thực tế phụ thuộc kích thước "
        "các nhóm. Kiểm tra pixel, dHash và xem ảnh hỗ trợ rà soát trùng trước huấn luyện. "
        "HAUI sử dụng cách chia hiện có, với lịch sử dùng tập test và các cặp cảnh train–validation "
        "gần giống đã nêu ở mục 3.4.2."
    )
    writer.table(
        "Bảng 3.8 Quy mô ảnh và đối tượng test của ba bộ dữ liệu",
        ["Bộ dữ liệu", "Ảnh train", "Ảnh validation", "Ảnh test", "Đối tượng test"],
        [(DATASET_NAMES[dataset], *[report["datasets"][dataset]["counts"][split]["images"]
                                  for split in ("train", "valid", "test")],
          report["datasets"][dataset]["counts"]["test"]["objects"])
         for dataset in DATASET_NAMES],
        [3.6, 2.7, 2.7, 2.7, 2.7],
    )
    subheading(writer, "3.4.7.2 Cấu hình kỹ thuật và phép đo")
    writer.p(
        f"Mỗi lượt train dùng {plan['epochs']} epoch, ảnh {plan['imgsz']} × {plan['imgsz']} pixel, "
        f"batch {plan['batch']}, CPU {plan['threads']} thread và seed {plan['seed']}. "
        "Recipe accuracy dùng AdamW với lr0 bằng 0,0005, cosine schedule, cls bằng 1,0, "
        "mosaic bằng 0,5, scale bằng 0,3, hsv_s bằng 0,4 và hsv_v bằng 0,3. Mosaic được tắt "
        "trong 10 epoch cuối. Các tham số này được áp dụng chung cho hai kiến trúc."
    )
    writer.p(
        "Checkpoint được chọn bằng mAP50–95 validation. P, R và F1 test được đo tại confidence "
        "chung 0,25, với đối sánh nhãn tại IoU 0,50 và NMS IoU 0,70. AP sử dụng confidence "
        "0,001 và TTA tắt. Dữ liệu, checkpoint, phiên bản thư viện và môi trường được ghi hash "
        "trong hồ sơ thực nghiệm. Đợt 30 epoch ở 640 pixel có ngân sách khác đợt 20 epoch ở "
        "416 pixel phía trên, nên ảnh hưởng của từng thay đổi tham số cần các phép ablation riêng."
    )
    subheading(writer, "3.4.7.3 Kết quả đối chiếu trên ba tập test")
    resumed = [DATASET_NAMES[dataset] for dataset, details in report["datasets"].items()
               if any(event.get("type") == "checkpoint_resume"
                      for event in (details.get("execution_interruptions") or {}).get("events", []))]
    if resumed:
        writer.p(
            "Quá trình huấn luyện có gián đoạn tại " + ", ".join(resumed) +
            ". Lượt chạy được khôi phục từ checkpoint với trạng thái optimizer và cấu hình gốc, "
            "giữ tổng số epoch đã định. Phần epoch chưa lưu được chạy lại. Nhật ký khôi phục "
            "và checkpoint trước khôi phục được lưu trong hồ sơ. Chuỗi số ngẫu nhiên sau khi "
            "khởi động lại có thể khác lượt chạy liên tục; đây là một giới hạn của đợt thực nghiệm."
        )
    writer.table(
        "Bảng 3.9 Chất lượng phát hiện của hai kiến trúc trên ba bộ dữ liệu",
        ["Bộ dữ liệu", "Mô hình", "P (%)", "R (%)", "F1 (%)", "mAP50 (%)", "mAP50–95 (%)"],
        [(DATASET_NAMES[row["dataset"]], MODEL_NAMES[row["model"]],
          *[percent(row[metric]) for metric in QUALITY_METRICS]) for row in rows],
        [2.8, 2.0, 1.8, 1.8, 1.8, 2.05, 2.15],
    )
    difference_rows = []
    for dataset, models in by_dataset.items():
        changes = [100 * (models["yolo11n"][key] - models["yolov8n"][key]) for key in QUALITY_METRICS]
        difference_rows.append((DATASET_NAMES[dataset], *[delta(value) for value in changes]))
        ap = changes[-1]
        f1 = changes[2]
        writer.p(
            f"Trên {DATASET_NAMES[dataset]}, chênh lệch mAP50–95 của YOLO11n so với YOLOv8n "
            f"là {delta(ap)} điểm phần trăm và chênh lệch F1 là {delta(f1)} điểm phần trăm. "
            f"YOLO11n có {models['yolo11n']['false_positives']} FP và {models['yolo11n']['false_negatives']} FN, "
            f"còn YOLOv8n có {models['yolov8n']['false_positives']} FP và {models['yolov8n']['false_negatives']} FN "
            "tại confidence đã ấn định."
        )
    writer.table(
        "Bảng 3.10 Chênh lệch YOLO11n so với YOLOv8n tính bằng điểm phần trăm",
        ["Bộ dữ liệu", "P", "R", "F1", "mAP50", "mAP50–95"],
        difference_rows, [3.4, 2.2, 2.2, 2.2, 2.2, 2.2],
    )
    writer.p(
        "Dấu dương ở Bảng 3.10 thể hiện chỉ số cao hơn của YOLO11n, dấu âm thể hiện chỉ số "
        "cao hơn của YOLOv8n. Kết quả được giữ theo từng bộ dữ liệu và từng tiêu chí. "
        "Một seed và số nhóm chụp hữu hạn giới hạn phạm vi kết luận về độ ổn định của chênh lệch."
    )
    subheading(writer, "3.4.7.4 Chi phí xử lý và minh họa đầu ra")
    writer.table(
        "Bảng 3.11 Quy mô và thời gian suy luận của sáu checkpoint",
        ["Bộ dữ liệu", "Mô hình", "Tham số (triệu)", "Checkpoint (MB)", "Suy luận (ms/ảnh)"],
        [(DATASET_NAMES[row["dataset"]], MODEL_NAMES[row["model"]], number(row["parameters"] / 1e6),
          number(row["checkpoint_mb"]), number(row["inference_ms"])) for row in rows],
        [2.4, 2.6, 3.1, 3.1, 3.2],
    )
    writer.p(
        "Thời gian trong Bảng 3.11 là suy luận trung bình mỗi ảnh của bước validation test theo "
        "batch trên CPU. Chi phí đo trong điều kiện phần cứng và phiên bản thư viện đã lưu. "
        "Các ảnh minh họa được chọn theo thứ tự tên tệp có ít nhất hai đối tượng được gán nhãn "
        "trước khi đọc kết quả của đợt mở rộng. Hai mô hình của mỗi bộ dùng cùng ảnh và cùng "
        "cấu hình suy luận. Bảng 3.9 tổng hợp đánh giá trên toàn tập test của bộ tương ứng."
    )
    for index, dataset in enumerate(DATASET_NAMES, start=4):
        writer.image(root / dataset / "sample_prediction/side_by_side.jpg",
                     f"Hình 3.{index} YOLO11n và YOLOv8n trên cùng ảnh minh họa của {DATASET_NAMES[dataset]}")
    # Keep figure numbering contiguous with a compact comparison chart before the examples.
    # The chart is generated from the same verified six rows by the finisher.
    chart = root / "comparison_three_datasets.png"
    if chart.is_file():
        chart_anchor = next(p for p in document.paragraphs if p.text.startswith("3.4.7.4 "))
        Writer(document, chart_anchor._p).image(chart, "Hình 3.3 mAP50–95 và F1 trên ba bộ dữ liệu")
    else:
        raise FileNotFoundError(chart)
    replace_paragraph(
        document, "Chương này cập nhật thực nghiệm theo mã nguồn VisionSortAI",
        "Chương này cập nhật thực nghiệm theo mã nguồn VisionSortAI hiện tại, gồm đối chứng "
        "YOLO11n–YOLOv8n trên dữ liệu HAUI và đợt mở rộng trên ba bộ dữ liệu ở mục 3.4.7. "
        "Các kết quả ResNet50 và detector bộ phận được trình bày theo hồ sơ thực nghiệm tương ứng.",
    )
    ap_wins = sum(models["yolo11n"]["map50_95"] > models["yolov8n"]["map50_95"]
                  for models in by_dataset.values())
    f1_wins = sum(models["yolo11n"]["f1"] > models["yolov8n"]["f1"]
                  for models in by_dataset.values())
    discussion = next(p for p in document.paragraphs if p.style.name == "Heading 2"
                      and p.text.startswith("3.11 "))
    Writer(document, discussion._p.getnext()).p(
        f"Trong đợt mở rộng với {plan['epochs']} epoch ở {plan['imgsz']} pixel, YOLO11n có "
        f"mAP50–95 cao hơn YOLOv8n trên {ap_wins}/3 bộ dữ liệu và F1 cao hơn trên {f1_wins}/3 bộ. "
        "Các giá trị và chênh lệch theo từng tiêu chí được trình bày ở mục 3.4.7. "
        "Phạm vi kết quả gắn với một seed, các nhóm chia tập và nhiệm vụ một lớp đã định nghĩa."
    )
    appendix_heading = next(p for p in document.paragraphs if p.style.name == "Heading 1"
                            and p.text.startswith("PHỤ LỤC HỒ SƠ"))
    references = Writer(document, appendix_heading._p)
    references.p('[16] Proença, P. F. và Simões, P. (2019), “TACO Trash Annotations in Context Dataset”, '
                 'bản v0.2, Zenodo. https://doi.org/10.5281/zenodo.3354286.')
    references.p('[17] Kraft, M., Piechocki, M., Ptak, B. và Walas, K. (2021), “UAVVaste dataset”, '
                 'bản v1, Zenodo. https://doi.org/10.5281/zenodo.8214061.')
    appendix = Writer(document, document.element.body.sectPr)
    appendix.p("A.7 HỒ SƠ SO SÁNH TRÊN BA BỘ DỮ LIỆU", "Heading 2")
    appendix.p(
        "Hồ sơ nằm tại outputs/yolo-three-datasets-20261115 trong VisionSortAI/ModelAI. "
        "study_plan.json lưu thiết kế, comparison_three_datasets.json và CSV lưu kết quả. "
        "Mỗi thư mục haui, taco, uavvaste có protocol.json, data_audit.json, nhật ký epoch "
        "và checkpoint của cả hai mô hình. Nguồn dữ liệu công khai và hình học annotation "
        "được truy vết bằng source.json và checksum của các gói chính thức."
    )
    for row in rows:
        paragraph = appendix.p(f"{DATASET_NAMES[row['dataset']]} {MODEL_NAMES[row['model']]} có SHA-256\n{row['checkpoint_sha256']}")
        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        paragraph.paragraph_format.first_line_indent = Pt(0)
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(4)
        paragraph.paragraph_format.line_spacing = 1.1
        for run in paragraph.runs:
            run.font.size = Pt(12)
    update = OxmlElement("w:updateFields")
    update.set(qn("w:val"), "true")
    document.settings.element.append(update)
    args.output.mkdir(parents=True, exist_ok=True)
    full_path = args.output / "De_an_Vu_Duc_Dung_so_sanh_3_bo_du_lieu.docx"
    document.save(full_path)
    chapter = Document(full_path)
    body = list(chapter.element.body)
    start = next(i for i, node in enumerate(body) if node.tag == qn("w:p")
                 and text_of(node).startswith("CHƯƠNG 3 ") and i > 200)
    end = next(i for i in range(start + 1, len(body)) if body[i].tag == qn("w:p")
               and text_of(body[i]).startswith("KẾT LUẬN VÀ KHUYẾN NGHỊ"))
    keep = body[start:end]
    section = copy.deepcopy(chapter.element.body.sectPr)
    for node in list(chapter.element.body):
        chapter.element.body.remove(node)
    for node in keep:
        chapter.element.body.append(node)
    chapter.element.body.append(section)
    chapter.save(args.output / "Chuong_3_so_sanh_3_bo_du_lieu.docx")
    print(full_path)


if __name__ == "__main__":
    main()
