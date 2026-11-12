from __future__ import annotations

import os
from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
DOCX_PATH = ROOT / "社交场景多模态UGC搜索与推荐系统方案.docx"
TMP_PATH = ROOT / "reports" / "_section_6_2_update.tmp.docx"

FONT_CN = "Microsoft YaHei"
FONT_LATIN = "Arial"
DARK_BLUE = "1F4E78"
PALE_BLUE = "EAF2F8"
BORDER = "D9D9D9"
MARKER = "标签背包按行为事件增量更新"


def set_run_font(run, size: float = 11, bold: bool = False, color: str = "000000") -> None:
    run.font.name = FONT_LATIN
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.rFonts
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    fonts.set(qn("w:ascii"), FONT_LATIN)
    fonts.set(qn("w:hAnsi"), FONT_LATIN)
    fonts.set(qn("w:eastAsia"), FONT_CN)


def style_paragraph(paragraph, *, bold: bool = False, keep_next: bool = False) -> None:
    paragraph.paragraph_format.space_after = Pt(6)
    paragraph.paragraph_format.line_spacing = 1.25
    paragraph.paragraph_format.keep_with_next = keep_next
    for run in paragraph.runs:
        set_run_font(run, size=11, bold=bold)


def insert_paragraph(anchor, text: str, *, bold: bool = False, keep_next: bool = False):
    paragraph = anchor.insert_paragraph_before(text)
    style_paragraph(paragraph, bold=bold, keep_next=keep_next)
    return paragraph


def set_cell_fill(cell, color: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), color)


def set_cell_margins(cell, value: int = 100) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for tag in ("top", "start", "bottom", "end"):
        node = tc_mar.find(qn(f"w:{tag}"))
        if node is None:
            node = OxmlElement(f"w:{tag}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_borders(table) -> None:
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = borders.find(qn(f"w:{edge}"))
        if element is None:
            element = OxmlElement(f"w:{edge}")
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "4")
        element.set(qn("w:color"), BORDER)


def set_repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    repeat = OxmlElement("w:tblHeader")
    repeat.set(qn("w:val"), "true")
    tr_pr.append(repeat)


def insert_table(anchor, doc, headers: list[str], rows: list[list[str]], widths: list[float]):
    table = doc.add_table(rows=1, cols=len(headers))
    table.autofit = False
    table.alignment = 1
    set_table_borders(table)
    set_repeat_header(table.rows[0])

    for index, text in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.width = Cm(widths[index])
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        set_cell_fill(cell, DARK_BLUE)
        set_cell_margins(cell)
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = paragraph.add_run(text)
        set_run_font(run, size=9.5, bold=True, color="FFFFFF")

    for row_index, values in enumerate(rows):
        row = table.add_row()
        for column_index, value in enumerate(values):
            cell = row.cells[column_index]
            cell.width = Cm(widths[column_index])
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            set_cell_margins(cell)
            set_cell_fill(cell, PALE_BLUE if row_index % 2 else "FFFFFF")
            paragraph = cell.paragraphs[0]
            paragraph.alignment = (
                WD_ALIGN_PARAGRAPH.CENTER if column_index < 2 else WD_ALIGN_PARAGRAPH.LEFT
            )
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.line_spacing = 1.15
            run = paragraph.add_run(str(value))
            set_run_font(run, size=9.2)

    anchor._p.addprevious(table._tbl)
    return table


def replace_sensitive_attribute_policy(doc: Document) -> None:
    old = (
        "年龄、性别等敏感属性只宜低权重使用，并需要经过隐私、合规和公平性评估。"
    )
    new = (
        "年龄、性别等敏感属性不直接作为兴趣标签或排序权重；如未来使用，必须先完成隐私、合规和公平性评估。"
    )
    for paragraph in doc.paragraphs:
        if paragraph.text.startswith("系统先为每个用户建立可解释的初始画像") and old in paragraph.text:
            text = paragraph.text.replace(old, new)
            for run in paragraph.runs:
                run._element.getparent().remove(run._element)
            run = paragraph.add_run(text)
            set_run_font(run)
            paragraph.paragraph_format.space_after = Pt(6)
            paragraph.paragraph_format.line_spacing = 1.25
            return


def main() -> None:
    doc = Document(DOCX_PATH)
    if any(MARKER in paragraph.text for paragraph in doc.paragraphs):
        raise SystemExit("第6.2节已经包含标签背包更新逻辑，未重复写入")

    anchor = next(
        paragraph for paragraph in doc.paragraphs if paragraph.text.startswith("6.3 ")
    )
    replace_sensitive_attribute_policy(doc)

    insert_paragraph(anchor, MARKER, bold=True, keep_next=True)
    insert_paragraph(
        anchor,
        "每条曝光、点击、停留、收藏、关注、发布和负反馈都应写入带有event_id、user_id、ugc_id、event_type、event_time和曝光位置的行为事件。系统先读取对应UGC的标签及置信度，再计算本次标签增量。仅曝光不直接改变兴趣；同一event_id只处理一次，防止消息重放导致权重重复累加。",
    )
    insert_paragraph(
        anchor,
        "本次标签增量等于行为强度、UGC标签置信度、停留质量、位置校正和重复行为衰减五项的乘积。下表给出第一版启发式强度，实际数值应在获得真实日志后通过离线评估和A B测试校准。",
    )
    insert_table(
        anchor,
        doc,
        ["行为", "初始强度", "更新对象与处理"],
        [
            ["仅曝光", "0", "记录曝光，不直接改变兴趣权重"],
            ["点击", "+0.05", "小幅更新消费标签"],
            ["有效停留", "+0.10", "按停留质量更新消费标签"],
            ["完播", "+0.15", "更新消费标签，需考虑内容时长"],
            ["点赞", "+0.20", "明显更新消费标签"],
            ["收藏或分享", "+0.30", "强更新消费标签"],
            ["关注或搜索后点击", "+0.35", "更新消费标签及作者偏好"],
            ["发布UGC", "+0.40", "更新创作标签，不等量写入消费标签"],
            ["快速划走", "-0.05", "多次出现后写入弱负向标签"],
            ["不感兴趣", "-0.40", "写入主题、作者或内容级负向标签"],
            ["举报", "-0.80", "进入安全处理，并区分违规反馈与主题偏好"],
        ],
        [3.2, 2.0, 10.4],
    )

    insert_paragraph(anchor, "标签权重与时间尺度", bold=True, keep_next=True)
    insert_paragraph(
        anchor,
        "更新前先按距离上次更新时间的间隔衰减旧权重，再加入本次标签增量，并将结果截断到0至1。会话、短期和长期权重分别更新，避免一次行为永久改变长期画像。正向权重与负向权重分开保存，排序时再计算有效兴趣，防止一次负反馈直接删除长期偏好。",
    )
    insert_table(
        anchor,
        doc,
        ["画像层", "建议衰减周期", "更新原则"],
        [
            ["会话兴趣", "2至6小时", "完整接收当前行为增量，快速更新并快速衰减"],
            ["短期兴趣", "3至14天", "接收部分增量，反映近期连续偏好"],
            ["长期兴趣", "60至180天", "只吸收稳定且重复出现的高质量证据"],
            ["负向兴趣", "7至90天", "按反馈强度设置有效期；举报另走安全链路"],
        ],
        [3.0, 3.0, 9.6],
    )

    insert_paragraph(anchor, "标签来源与冲突处理", bold=True, keep_next=True)
    insert_paragraph(
        anchor,
        "浏览、搜索、停留和收藏更新consumer_tag_bag；用户发帖解析出的标签更新creator_tag_bag；快速划走、不感兴趣和屏蔽更新negative_tag_bag。创作兴趣与消费兴趣不得直接合并，因为用户发布某类内容不等于希望持续消费同类内容。人口属性保留在demographic_context中，不通过行为事件转换为兴趣标签。",
    )
    insert_paragraph(
        anchor,
        "同一主题的重复行为采用递减增量，防止连续点击把单个标签迅速推到上限。标签更新还应保留证据次数、来源、最后事件、更新时间和模型版本；在线服务执行低延迟增量更新，离线任务按日重算、去重、归一化、清理低权重标签并校验版本。",
    )

    insert_paragraph(anchor, "冷启动向行为画像过渡", bold=True, keep_next=True)
    insert_paragraph(
        anchor,
        "最终画像由注册兴趣先验和行为画像加权组成。随着有效行为增加，注册兴趣逐步降权，但保留少量回退能力；行为不足或行为画像失效时，系统仍可使用初始兴趣和安全热门内容。",
    )
    insert_table(
        anchor,
        doc,
        ["有效行为数量", "冷启动先验", "行为画像"],
        [
            ["0至5次", "80%", "20%"],
            ["6至20次", "50%", "50%"],
            ["21至100次", "20%", "80%"],
            ["100次以上", "5%", "95%"],
        ],
        [5.2, 5.2, 5.2],
    )
    insert_paragraph(
        anchor,
        "上述阈值和行为强度属于第一版工程规则。上线前需要检查曝光偏差、位置偏差、不同内容时长、标签置信度和用户群体差异，并通过时间切分的离线验证与稳定分桶的在线实验确定最终参数。",
    )

    TMP_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(TMP_PATH)
    os.replace(TMP_PATH, DOCX_PATH)
    print(DOCX_PATH)


if __name__ == "__main__":
    main()
