"""Update chapter 3 from measured benchmark artifacts; run with bundled docx runtime.

No metrics are embedded here: authoring fails until complete real reports exist.
"""
import argparse
import copy
import json
import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


def text_of(element):
    return "".join(element.xpath(".//w:t/text()"))


def percent(value, digits=2):
    return f"{100*value:.{digits}f}".replace(".", ",")


def number(value, digits=2):
    return f"{value:.{digits}f}".replace(".", ",")


def style_table(table, widths):
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for column, width in zip(table.columns, widths):
        column.width = Cm(width)
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        border = OxmlElement("w:"+edge)
        for key, value in (("val", "single"), ("sz", "4"), ("color", "D9D9D9")):
            border.set(qn("w:"+key), value)
        borders.append(border)
    table._tbl.tblPr.append(borders)
    for row_index, row in enumerate(table.rows):
        tr_pr = row._tr.get_or_add_trPr()
        no_split = OxmlElement("w:cantSplit")
        tr_pr.append(no_split)
        if row_index == 0:
            tr_pr.append(OxmlElement("w:tblHeader"))
        for col, cell in enumerate(row.cells):
            cell.width = Cm(widths[col])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            props = cell._tc.get_or_add_tcPr()
            shade = OxmlElement("w:shd")
            shade.set(qn("w:fill"), "E8EDF2" if row_index == 0 else ("F6F7F8" if row_index % 2 == 0 else "FFFFFF"))
            props.append(shade)
            margins = OxmlElement("w:tcMar")
            for side in ("top", "left", "bottom", "right"):
                margin = OxmlElement("w:"+side)
                margin.set(qn("w:w"), "85")
                margin.set(qn("w:type"), "dxa")
                margins.append(margin)
            props.append(margins)
            for paragraph in cell.paragraphs:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT if col == 0 else WD_ALIGN_PARAGRAPH.CENTER
                paragraph.paragraph_format.space_before = Pt(2)
                paragraph.paragraph_format.space_after = Pt(2)
                paragraph.paragraph_format.line_spacing = 1.05
                paragraph.paragraph_format.left_indent = Cm(0)
                paragraph.paragraph_format.right_indent = Cm(0)
                paragraph.paragraph_format.first_line_indent = Cm(0)
                paragraph.paragraph_format.keep_with_next = row_index == 0
                for run in paragraph.runs:
                    run.font.name = "Times New Roman"
                    run.font.size = Pt(11)
                    run.font.color.rgb = RGBColor(0, 0, 0)
                    run.bold = row_index == 0


class Writer:
    def __init__(self, document, anchor):
        self.document, self.anchor = document, anchor

    def p(self, text, style="Normal"):
        p = self.document.add_paragraph(text, style=style)
        self.anchor.addprevious(p._p)
        if style.startswith("Heading"):
            p.paragraph_format.keep_with_next = True
        return p

    def caption(self, text, figure=False):
        style = "hình ảnh" if figure else "bảng biểu"
        if style not in self.document.styles:
            style = "Caption"
        paragraph = self.p(text, style)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if figure else WD_ALIGN_PARAGRAPH.LEFT
        paragraph.paragraph_format.first_line_indent = Cm(0)
        paragraph.paragraph_format.keep_with_next = not figure
        for run in paragraph.runs:
            run.font.color.rgb = RGBColor(0, 0, 0)
            run.italic = not figure
        return paragraph

    def table(self, title, headers, rows, widths):
        self.caption(title)
        table = self.document.add_table(rows=1, cols=len(headers))
        for cell, label in zip(table.rows[0].cells, headers):
            cell.text = label
        for row in rows:
            for cell, value in zip(table.add_row().cells, row):
                cell.text = str(value)
        style_table(table, widths)
        self.anchor.addprevious(table._tbl)
        self.p("")

    def image(self, path, caption):
        p = self.p("")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.first_line_indent = Cm(0)
        p.paragraph_format.keep_with_next = True
        p.add_run().add_picture(str(path), width=Cm(14.4))
        self.caption(caption, figure=True)


def replace_paragraph(document, prefix, text):
    for paragraph in document.paragraphs:
        if paragraph.style.name.startswith("toc"):
            continue
        if paragraph.text.startswith(prefix):
            paragraph.text = text
            return
    raise ValueError(f"Missing paragraph: {prefix}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.experiment.resolve()
    protocol = json.loads((root/"protocol.json").read_text(encoding="utf-8"))
    if protocol["status"] != "complete":
        raise ValueError("Finish training and test evaluation before authoring results")
    report = json.loads((root/"comparison.json").read_text(encoding="utf-8"))
    demo = json.loads((root/"sample_prediction/predictions.json").read_text(encoding="utf-8"))
    audit = json.loads((root/"data_audit.json").read_text(encoding="utf-8"))
    settings = report["settings"]
    rows = report["results"]
    controlled = [r for r in rows if r["role"] == "controlled"]
    interrupted = set(report.get("execution_interruptions", {}).get("interrupted_models", []))
    names = {"yolo11n": "YOLO11n", "yolov8n": "YOLOv8n", "existing_yolo11": "YOLO11 hiện tại"}
    winner = report["conclusion"]["winner"]
    gap = report["conclusion"]["difference_percentage_points"]
    document = Document(args.source)
    # Preserve existing design, figures and content outside the requested chapter.
    for paragraph in document.paragraphs:
        if paragraph.style.name.startswith("toc"):
            continue
        original = paragraph.text
        revised = re.sub(r"Bảng 3\.([4-8])(?!\d)", lambda m: "Bảng 3."+str(int(m[1])+4), original).replace("Java 25", "Java 21")
        revised = revised.replace("Hình 3.2", "Hình 3.3")
        if revised != original:
            for run in paragraph.runs:
                run.text = re.sub(r"Bảng 3\.([4-8])(?!\d)", lambda m: "Bảng 3."+str(int(m[1])+4), run.text).replace("Hình 3.2", "Hình 3.3").replace("Java 25", "Java 21")
            if paragraph.text != revised:
                paragraph.text = revised
    start = next(p for p in document.paragraphs if p.style.name == "Heading 2" and p.text.startswith("3.4 "))
    stop = next(p for p in document.paragraphs if p.style.name == "Heading 2" and p.text.startswith("3.5 "))
    node = start._p
    while node is not stop._p:
        following = node.getnext()
        node.getparent().remove(node)
        node = following
    writer = Writer(document, stop._p)
    writer.p("3.4 SO SÁNH YOLO11 VÀ YOLOV8 TRÊN CÙNG BỘ DỮ LIỆU", "Heading 2")
    writer.p("3.4.1 Mục tiêu và thiết kế đối chứng", "Heading 3")
    writer.p("Thực nghiệm so sánh chất lượng định vị đối tượng của YOLO11n và YOLOv8n trên cùng tập ảnh có nhãn và cùng ngân sách huấn luyện. Hai mô hình bắt đầu từ checkpoint COCO pretrained 80 lớp tương ứng, sau đó học bài toán phát hiện một lớp item. Biến thể nano được chọn cho cả hai kiến trúc. Số tham số và chi phí xử lý được đo trực tiếp từ từng checkpoint.")
    writer.p("Thiết kế đánh giá tham khảo cách trình bày của Jin và cộng sự [14], gồm dữ liệu, nền tảng thực nghiệm, chất lượng nhận dạng và chi phí xử lý. Nghiên cứu này áp dụng cách đánh giá đó cho khung phát hiện YOLO bằng Precision, Recall, F1 và mAP trên bộ dữ liệu của dự án [10], [15].")
    writer.p("Checkpoint YOLO11n của dịch vụ AI tại thời điểm bắt đầu thực nghiệm cũng được đánh giá trên cùng tập test và cùng cấu hình suy luận. Lịch sử fine-tune của checkpoint này được ghi nhận trong vai trò tham chiếu triển khai. Hai lượt huấn luyện từ COCO pretrained cung cấp phép đối chứng với ngân sách và điều kiện chung.")
    writer.p("3.4.2 Dữ liệu và kiểm soát điều kiện thực nghiệm", "Heading 3")
    counts = report["counts"]
    writer.p(f"Hai mô hình dùng chung {counts['train']['images']:,} ảnh train với {counts['train']['objects']:,} đối tượng, {counts['valid']['images']} ảnh validation với {counts['valid']['objects']} đối tượng và {counts['test']['images']} ảnh test với {counts['test']['objects']} đối tượng. Bản dữ liệu thực nghiệm được tạo từ cách chia sẵn có của dự án. Các ID vật liệu gốc 0–3 được quy về một lớp phát hiện item. Tổng cộng 8 hàng polygon train, 2 hàng validation và 2 hàng test được chuyển thành hình chữ nhật bao ngoài.")
    writer.p(f"Kiểm tra pixel ghi nhận 0 cặp ảnh trùng hoàn toàn giữa các split. Kiểm tra dHash 64 bit với khoảng cách tối đa 4 ghi nhận {len(audit['near_duplicate_candidates'])} cặp train–validation có cảnh chụp gần giống nhau. Các cặp này cho thấy nguy cơ tương quan giữa mẫu huấn luyện và validation. Tập test 182 ảnh đã được sử dụng trong lịch sử đánh giá của dự án. Những đặc điểm này giới hạn phạm vi khái quát của kết quả.")
    writer.p(f"Bản dữ liệu có SHA-256 {protocol['dataset_sha256']}. Hash kết hợp đường dẫn với nội dung ảnh và nhãn, được kiểm tra trước huấn luyện và trước đánh giá. Checkpoint được chọn bằng mAP50–95 validation. Các tham số đánh giá test được ấn định trong protocol.json trước khi đọc kết quả.")
    environment = protocol.get("evaluation_environment", protocol["environment"])
    writer.table("Bảng 3.3 Điều kiện chung của hai lượt huấn luyện", ["Tham số", "Giá trị"], [
        ("Mô hình khởi tạo", "YOLO11n và YOLOv8n, COCO pretrained"),
        ("Epoch và kích thước ảnh", f"{settings['epochs']} epoch, {settings['imgsz']} × {settings['imgsz']} pixel"),
        ("Batch và thiết bị", f"{settings['batch']}, CPU với {settings['threads']} thread"),
        ("Seed và bộ tối ưu", f"Seed {settings['seed']}, AdamW, lr0 = 0,001, cosine schedule"),
        ("Augmentation", "Mosaic, HSV, dịch chuyển, co giãn và lật ngang giống nhau"),
        ("Chọn checkpoint", f"mAP50–95 validation cao nhất sau đủ {settings['epochs']} epoch"),
        ("Ngưỡng đánh giá", "Confidence tính AP 0,001, confidence P/R/F1 0,25, NMS IoU 0,70"),
        ("Môi trường", f"Python {environment['python']}, PyTorch {environment['torch']}, Ultralytics {environment['ultralytics']}"),
        ("Phần cứng", f"CPU {environment['cpu_count']} luồng logic, RAM {number(environment['memory_bytes']/1024**3, 1)} GiB"),
        ("Cache ảnh", "Ảnh được cache trong RAM cho cả hai mô hình")], [4.2, 10.2])
    writer.p(f"Đợt chạy sử dụng ngân sách {settings['epochs']} epoch ở {settings['imgsz']} pixel theo khả năng CPU của máy thực nghiệm. Kết quả trong chương gắn với ngân sách này và seed {settings['seed']}. Phiên bản thư viện, phần cứng và cache RAM cũng ảnh hưởng khả năng tái lập. Mã nguồn cung cấp thêm lệnh cấu hình 100 epoch ở 640 pixel để thực hiện đợt nghiên cứu mở rộng.")
    writer.p("3.4.3 Kết quả trên cùng tập test", "Heading 3")
    writer.table("Bảng 3.4 AP và Precision Recall tại điểm F1 lớn nhất trên tập test", ["Mô hình", "P tại max F1 (%)", "R tại max F1 (%)", "mAP50 (%)", "mAP50–95 (%)"],
                 [(names[r['name']], percent(r['precision_max_f1']), percent(r['recall_max_f1']), percent(r['map50']), percent(r['map50_95'])) for r in rows], [4.0, 2.6, 2.6, 2.6, 2.6])
    if winner == "tie":
        writer.p("Hai lượt huấn luyện có mAP50–95 test bằng nhau trong độ chính xác số đã lưu.")
    else:
        writer.p(f"Theo tiêu chí mAP50–95 trên tập test, {names[winner]} cao hơn {number(gap, 3)} điểm phần trăm trong đợt chạy một seed này. Đánh giá ý nghĩa thống kê cần các lần lặp bổ sung.")
    writer.p("P và R tại max F1 trong Bảng 3.4 được Ultralytics tổng hợp từ đường cong của từng mô hình. Bảng 3.5 sử dụng confidence chung 0,25 để đo TP, FP, FN, Precision, Recall và F1. Mỗi dự đoán được đối sánh lại với nhãn chuẩn tại IoU 0,50 sau khi lọc confidence. NMS sử dụng IoU 0,70 để xử lý các khung chồng lấn.")
    writer.table("Bảng 3.5 Kết quả phát hiện tại cùng confidence 0,25 và IoU khớp nhãn 0,50", ["Mô hình", "TP", "FP", "FN", "P (%)", "R (%)", "F1 (%)"],
                 [(names[r['name']], r['fixed_confidence']['true_positives'],
                   r['fixed_confidence']['predictions']-r['fixed_confidence']['true_positives'],
                   r['fixed_confidence']['objects']-r['fixed_confidence']['true_positives'],
                   percent(r['fixed_confidence']['precision']), percent(r['fixed_confidence']['recall']), percent(r['fixed_confidence']['f1'])) for r in rows], [4.0, 1.1, 1.1, 1.1, 2.35, 2.35, 2.4])
    fixed11 = next(r for r in controlled if r['name'] == 'yolo11n')['fixed_confidence']
    fixed8 = next(r for r in controlled if r['name'] == 'yolov8n')['fixed_confidence']
    miss_difference = fixed8['true_positives'] - fixed11['true_positives']
    extra_difference = (fixed11['predictions']-fixed11['true_positives']) - (fixed8['predictions']-fixed8['true_positives'])
    miss_text = (f"{'YOLOv8n' if miss_difference > 0 else 'YOLO11n'} bỏ sót ít hơn mô hình còn lại {abs(miss_difference)} đối tượng." if miss_difference else "Hai mô hình có số đối tượng bỏ sót bằng nhau.")
    extra_text = (f"{'YOLOv8n' if extra_difference > 0 else 'YOLO11n'} có ít hơn mô hình còn lại {abs(extra_difference)} khung dự đoán sai theo đối sánh IoU 0,50." if extra_difference else "Hai mô hình có cùng số khung dự đoán sai.")
    writer.p(miss_text + " " + extra_text + " F1 tổng hợp mức đánh đổi giữa Precision và Recall tại confidence 0,25. Confidence biểu thị điểm của từng dự đoán. mAP và P/R/F1 được tính bằng cách đối chiếu với các nhãn chuẩn của tập test.")
    writer.p("3.4.4 Diễn biến huấn luyện và chi phí xử lý", "Heading 3")
    writer.image(root/"training_comparison.png", "Hình 3.1 Diễn biến mAP50–95 validation và box loss train của hai mô hình")
    writer.table("Bảng 3.6 Quy mô mô hình và chi phí thực nghiệm trên CPU", ["Mô hình", "Tham số (triệu)", "Checkpoint (MB)", "Train (phút)", "Suy luận batch (ms/ảnh)"],
                 [(names[r['name']], number(r['parameters']/1e6), number(r['checkpoint_mb']),
                   ("Có gián đoạn" if r['name'] in interrupted else number(protocol['training_seconds'][r['name']]/60)) if r['role']=='controlled' else "Khác lịch sử",
                   number(r['speed_ms_per_image']['inference'])) for r in rows], [4.0, 2.6, 2.6, 2.6, 2.6])
    writer.p("Bảng 3.6 trình bày thời gian suy luận trung bình mỗi ảnh do Ultralytics đo trên tập test với batch 8. Dung lượng checkpoint được tính bằng số byte chia 10⁶. Số tham số được đếm từ checkpoint trước khi fuse các lớp phục vụ suy luận. Thời gian train bao gồm các bước validation của từng lượt.")
    if interrupted:
        writer.p("YOLO11n bị gián đoạn dài trong epoch 5 giữa ngày 11 và 12/11/2026. Tổng thời gian tường của lượt này chứa khoảng gián đoạn, nên bảng ghi trạng thái gián đoạn ở cột thời gian train. protocol.json và execution_interruptions.json lưu bằng chứng thời gian. Các chỉ số suy luận được đo sau khi cả hai mô hình hoàn tất huấn luyện.")
    writer.p("3.4.5 Đối chiếu hai mô hình trên cùng một ảnh", "Heading 3")
    writer.p("Ảnh minh họa được chọn trước khi đọc kết quả huấn luyện bằng cách lấy ảnh đầu tiên theo thứ tự tên tệp có ít nhất hai đối tượng được gán nhãn trong tập test. Hai mô hình sử dụng cùng nội dung ảnh, kích thước đầu vào, confidence 0,25 và NMS IoU 0,70. TTA được đặt ở trạng thái tắt.")
    writer.image(root/"sample_prediction/side_by_side.jpg", "Hình 3.2 Kết quả YOLO11n và YOLOv8n trên cùng một ảnh test đã chọn trước")
    writer.table("Bảng 3.7 Đầu ra của hai mô hình trên ảnh minh họa", ["Mô hình", "Số khung", "Confidence từng khung (%)", "Median predict (ms)"],
                 [("YOLO11n" if r['name']=='yolo11' else "YOLOv8n", r['detection_count'],
                   ", ".join(percent(d['confidence']) for d in r['detections']) or "0 khung",
                   number(r['median_predict_ms'])) for r in demo['models']], [3.4, 1.8, 6.0, 3.2])
    writer.p("Thời gian predict là median của 10 lần chạy sau 2 lần làm nóng, gồm tiền xử lý, suy luận và NMS. Đầu vào của phép đo là mảng pixel đã đọc vào bộ nhớ và checkpoint đã nạp. predictions.json lưu tọa độ xyxy cùng confidence của mọi khung. Hình minh họa thể hiện hành vi trên một ảnh, còn các bảng mAP và P/R/F1 tổng hợp kết quả trên 182 ảnh có nhãn.")
    writer.p("3.4.6 Khả năng tái lập và giới hạn kết luận", "Heading 3")
    writer.p("Hồ sơ thực nghiệm gồm protocol.json, data_audit.json, results.csv của từng lượt, checkpoint best.pt, comparison.json và comparison.csv. Việc đánh giá test nạp trực tiếp checkpoint có mAP50–95 validation cao nhất. Hash dữ liệu và checkpoint giúp truy vết từng kết quả.")
    writer.p("Mô-đun trashsmart.yolo_training.predict_compare hỗ trợ --model yolo11 và --model yolov8 để chạy từng mô hình với cùng --image. Tham số --model both tạo ảnh đặt cạnh nhau. Hướng dẫn BENCHMARK.md cung cấp các lệnh chuẩn bị dữ liệu, huấn luyện, đánh giá và thử ảnh trên máy cục bộ.")
    writer.p(f"Kết quả có phạm vi một lớp phát hiện, ngân sách {settings['epochs']} epoch trên CPU và một seed. Các cặp ảnh train–validation có cảnh gần giống nhau cùng lịch sử sử dụng tập test là các hạn chế của bộ dữ liệu hiện có. Những đợt đánh giá mở rộng cần lặp nhiều seed và chia nhóm theo sản phẩm hoặc phiên chụp để đo khả năng khái quát.")
    empty_test = sum(not p.read_text(encoding="utf-8-sig").strip() for p in (root/"dataset/test/labels").glob("*.txt"))
    writer.p(f"Tập test có {empty_test} ảnh âm tính và {counts['test']['images']-empty_test} ảnh chứa đối tượng được gán nhãn. Việc đo báo động nhầm trên cảnh nền cần bổ sung ảnh âm tính với điều kiện thu thập được ghi rõ.")

    replace_paragraph(document, "Các mục 3.1–3.7 giữ hồ sơ", "Chương này cập nhật thực nghiệm theo mã nguồn VisionSortAI hiện tại và bổ sung đối chứng YOLO11n–YOLOv8n trên cùng bộ dữ liệu ở mục 3.4. Các kết quả ResNet50 và detector bộ phận được trình bày theo hồ sơ thực nghiệm tương ứng. Mỗi chỉ số gắn với nhiệm vụ, dữ liệu và checkpoint đã được đánh giá.")
    replace_paragraph(document, "Backend sử dụng Spring Boot,", "Backend sử dụng Spring Boot 3.5.9, Java 21, Spring Data JPA, Spring Security và MySQL. Dịch vụ nhận diện viết bằng Python, cung cấp API FastAPI và dùng YOLO định vị đối tượng trước khi ResNet50 phân loại chất liệu. FE gọi BE qua API, sau đó BE gửi ảnh tới dịch vụ AI và lưu kết quả. Cloudinary phục vụ lưu ảnh gốc và ảnh chú thích.")
    replace_paragraph(document, "Các tham số ghi trong args.yaml", f"Các nhật ký YOLO lịch sử lưu cấu hình 640 pixel, batch 8 và tối đa 100 epoch trên CPU với lịch sử khởi tạo và learning rate riêng. Đợt đối chứng mới dùng {settings['epochs']} epoch và {settings['imgsz']} pixel cho cả hai mô hình theo giao thức tại mục 3.4. Đo độ trễ FE–BE–AI và tải đồng thời cần công bố thêm điều kiện mạng cùng số yêu cầu xử lý.")
    replace_paragraph(document, "Đối với phát hiện, Precision biểu diễn", "Đối với phát hiện, Precision = TP/(TP + FP), Recall = TP/(TP + FN) và F1 = 2PR/(P + R). Mỗi dự đoán đúng phải thỏa điều kiện đối sánh khung bao bằng IoU. mAP50 tổng hợp AP tại IoU 0,50. mAP50–95 lấy trung bình trên mười ngưỡng từ 0,50 đến 0,95. Đợt đối chứng mục 3.4 đo test từ checkpoint được chọn bằng validation. Các bảng ghi rõ điểm P/R tại max F1 của Ultralytics và điểm P/R/F1 tại confidence cố định.")
    # Refresh evidence rows and original data table without altering ResNet results.
    for table in document.tables:
        for row in table.rows:
            values = [cell.text for cell in row.cells]
            if values[0] == "Mô hình phát hiện chai":
                row.cells[1].text = "Giao thức khóa dữ liệu, hai lượt train và báo cáo test mới"
                row.cells[2].text = "So sánh YOLO11n–YOLOv8n cùng điều kiện và đo checkpoint API tham chiếu"
            if values[0] == "Phát hiện chai" and len(row.cells) == 5:
                row.cells[4].text = "182 ảnh test với 261 đối tượng, xem mục 3.4"
    replace_paragraph(document, "Luồng người dùng đã có mã tích hợp", "Luồng người dùng có đăng ký, đăng nhập, tải ảnh, xem kết quả và lịch sử qua API của BE. BE quản lý trạng thái lượt quét, quyền sở hữu và thao tác thử lại khi xử lý lỗi. Dịch vụ AI trả khung đối tượng, nhãn vật liệu, confidence và trạng thái cần xác nhận. Giao diện có thể trình bày bộ phận khi dịch vụ tương ứng được bật và có đầu ra.")
    replace_paragraph(document, "Giao diện camera có mã chụp ảnh", "FE sử dụng chức năng chụp hoặc chọn ảnh của trình duyệt và thiết bị. Giao diện Admin kết nối API cho tổng quan, lịch sử quét, thống kê, quản lý người dùng và hồ sơ quản trị. Đánh giá vận hành trên thiết bị thật cần ghi phiên bản ứng dụng, điều kiện mạng và phản hồi của toàn bộ luồng xử lý.")
    replace_paragraph(document, "Truy hồi tri thức sử dụng nhãn", "Mã nguồn có các thành phần tri thức và RAG từ các giai đoạn phát triển trước. Thực nghiệm tại mục 3.4 đánh giá lớp phát hiện đối tượng trong luồng FE–BE–AI hiện tại. Phương án đo chất lượng truy hồi, đồ thị tri thức và gợi ý xử lý được trình bày ở mục 3.10.")
    replace_paragraph(document, "Bộ kịch bản dưới đây được đề xuất", "Bộ kịch bản dưới đây phục vụ nghiệm thu các luồng FE–BE–AI. Mã nguồn có kiểm thử tự động cho backend, frontend và AI. Đợt đối chứng này đã chạy kiểm thử công cụ benchmark và suy luận ảnh thực. Mỗi ca nghiệm thu ứng dụng cần ghi phiên bản, dữ liệu đầu vào, phản hồi API và thay đổi dữ liệu, cùng phép đo tải đồng thời và độ trễ đầu cuối.")
    for table in document.tables:
        for row in table.rows:
            if len(row.cells) != 3:
                continue
            replacements = {
                "KT06": ("Thử lại lượt quét lỗi hoặc bấm lặp", "Đúng ID, quyền sở hữu, trạng thái và số detection được lưu"),
                "KT07": ("Từ chối camera hoặc chọn ảnh sai định dạng", "Thông báo lỗi đúng tình huống và giải phóng tài nguyên"),
                "KT08": ("Dịch vụ AI hoặc lưu ảnh gặp lỗi", "Lưu trạng thái lỗi và cung cấp thao tác thử lại"),
                "KT09": ("Tìm kiếm, lọc ngày, phân trang lịch sử và thống kê", "Kết quả theo dữ liệu BE, khoảng lọc và phạm vi người dùng"),
                "KT10": ("Phân quyền Admin và quản lý tài khoản", "Chặn truy cập trái quyền, khóa tài khoản và bảo vệ tài khoản quản trị")}
            if row.cells[0].text in replacements:
                row.cells[1].text, row.cells[2].text = replacements[row.cells[0].text]
    replace_paragraph(document, "Giới hạn chính gồm phạm vi YOLO", f"Phạm vi thực nghiệm gồm lớp phát hiện item, bộ phân loại bốn vật liệu và các hồ sơ đánh giá thành phần. Đợt đối chứng sử dụng một seed với {settings['epochs']} epoch cùng tập test hiện có. Ngân sách hữu hạn, tương quan giữa các cảnh chụp và lịch sử sử dụng test giới hạn khả năng khái quát của kết quả. Đánh giá toàn hệ thống cần thêm bằng chứng về giao diện, phân quyền, độ trễ và chất lượng gợi ý.")
    discussion = next(p for p in document.paragraphs if p.style.name == "Heading 2" and p.text.startswith("3.11 "))
    by_name = {row['name']: row for row in controlled}
    conclusion = (f"{names[winner]} đạt mAP50–95 cao hơn {number(gap, 3)} điểm phần trăm trong thiết lập này." if winner != 'tie' else "Hai mô hình chưa được phân biệt theo tiêu chí mAP50–95 đã chọn.")
    Writer(document, discussion._p.getnext()).p(
        f"Đợt đối chứng bổ sung sử dụng cùng dữ liệu, {settings['epochs']} epoch và kích thước {settings['imgsz']} pixel cho hai kiến trúc. "
        f"Trên 182 ảnh test, YOLO11n đạt mAP50–95 {percent(by_name['yolo11n']['map50_95'])}%, còn YOLOv8n đạt {percent(by_name['yolov8n']['map50_95'])}%. "
        + conclusion + f" Ở confidence 0,25, F1 của YOLO11n đạt {percent(fixed11['f1'])}% và YOLOv8n đạt {percent(fixed8['f1'])}%. Các kết quả này thể hiện đánh đổi giữa bỏ sót và phát hiện sai trong thiết lập đã đo.")
    bibliography = next(p for p in document.paragraphs if p.style.name == "Heading 1" and p.text.startswith("PHỤ LỤC HỒ SƠ"))
    references = Writer(document, bibliography._p)
    references.p('[14] Jin, S., Yang, Z., Królczyk, G., Liu, X., Gardoni, P. và Li, Z. (2023), “Garbage detection and classification using a new deep learning-based machine vision system as a tool for sustainable waste recycling”, Waste Management, 162, tr. 123–130. https://doi.org/10.1016/j.wasman.2023.02.014.')
    references.p('[15] Ultralytics (không ghi năm), “Explore Ultralytics YOLOv8”, tài liệu mô hình. https://docs.ultralytics.com/models/yolov8/ (truy cập 11/11/2026).')
    # Add reproducibility appendix before the final section properties.
    appendix_anchor = document.element.body.sectPr
    if appendix_anchor is None:
        raise ValueError("Missing document section settings")
    appendix = Writer(document, appendix_anchor)
    appendix.p("A.6 HỒ SƠ ĐỐI CHỨNG YOLO11 VÀ YOLOV8", "Heading 2")
    appendix.p("Hồ sơ nằm tại outputs/yolo11-vs-yolov8 trong VisionSortAI/ModelAI. protocol.json ghi giao thức, hash dữ liệu và môi trường. comparison.json cùng comparison.csv ghi kết quả test. Hai checkpoint là yolo11n/weights/best.pt và yolov8n/weights/best.pt. sample_prediction lưu ảnh cùng các khung dự đoán. Những tệp này cung cấp dữ liệu để kiểm tra lại số liệu của chương.")
    for row in rows:
        appendix.p(f"{names[row['name']]} có SHA-256 {row['checkpoint_sha256']}.")
    # Request Word to refresh fields when it opens the output copy.
    update = OxmlElement("w:updateFields")
    update.set(qn("w:val"), "true")
    document.settings.element.append(update)
    args.output.mkdir(parents=True, exist_ok=True)
    full_path = args.output/"De_an_Vu_Duc_Dung_cap_nhat_chuong_3.docx"
    document.save(full_path)
    # Standalone chapter retains the same relationships and formatting.
    chapter = Document(full_path)
    body = list(chapter.element.body)
    chapter_start = next(i for i,e in enumerate(body) if e.tag == qn("w:p") and text_of(e).startswith("CHƯƠNG 3 ") and i > 200)
    chapter_end = next(i for i in range(chapter_start+1, len(body)) if body[i].tag == qn("w:p") and text_of(body[i]).startswith("KẾT LUẬN VÀ KHUYẾN NGHỊ"))
    keep = body[chapter_start:chapter_end]
    section = copy.deepcopy(chapter.element.body.sectPr)
    for element in list(chapter.element.body):
        chapter.element.body.remove(element)
    for element in keep:
        chapter.element.body.append(element)
    chapter.element.body.append(section)
    for sec in chapter.sections:
        sec.header.is_linked_to_previous = False
        # Standalone chapter references remain numbered as in the full thesis.
    chapter.save(args.output/"Chuong_3_thuc_nghiem_YOLO11_YOLOv8.docx")
    print(full_path)


if __name__ == "__main__":
    main()
