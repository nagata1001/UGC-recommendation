from __future__ import annotations

import json
import os
import sys
from collections import OrderedDict
from pathlib import Path

from docx import Document
from docx.enum.text import WD_BREAK
from docx.shared import Pt


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from append_cold_start_report import add_body, add_bullet, add_heading, add_table, set_run_font


DOCX_PATH = ROOT / "社交场景多模态UGC搜索与推荐系统方案.docx"
REPORT_PATH = ROOT / "reports" / "hot_start_7d_simulation.json"
TMP_PATH = ROOT / "reports" / "_hot_start_docx_update.tmp.docx"
MARKER = "17 热启动行为回放实验报告"


EVENT_LABELS = OrderedDict(
    [
        ("impression", "仅曝光"),
        ("click", "点击"),
        ("dwell", "有效停留"),
        ("complete", "完播"),
        ("like", "点赞"),
        ("save", "收藏"),
        ("quick_skip", "快速划走"),
        ("not_interested", "不感兴趣"),
    ]
)


def add_bold_label(doc: Document, text: str):
    paragraph = doc.add_paragraph()
    run = paragraph.add_run(text)
    set_run_font(run, size=11, bold=True)
    paragraph.paragraph_format.space_before = Pt(7)
    paragraph.paragraph_format.space_after = Pt(4)
    paragraph.paragraph_format.keep_with_next = True
    return paragraph


def percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def main() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    doc = Document(DOCX_PATH)
    if any(MARKER in paragraph.text for paragraph in doc.paragraphs):
        raise SystemExit("方案已包含第17章，未重复写入")

    page_break = doc.add_paragraph()
    page_break.add_run().add_break(WD_BREAK.PAGE)
    add_heading(doc, MARKER, 1)
    add_body(
        doc,
        "本实验按时间顺序执行推荐、用户反馈、标签背包更新和重新推荐，验证系统进入热启动阶段后的完整闭环。6名模拟用户连续运行7天，每人每天获得10次曝光，共产生420条行为事件。全部事件均成功写入且事件编号唯一，6名用户最终均进入hot_start阶段。结果证明更新链路能够运行，但兴趣漂移的响应速度和冷启动先验的衰减速度仍需调参。",
    )

    add_heading(doc, "17.1 实验设计", 2)
    add_body(
        doc,
        "实验从发帖后的标签背包开始，每天先根据当前画像生成候选列表，再按模拟用户的潜在兴趣产生反馈。系统处理反馈后更新消费标签、会话标签或负向标签，并立即生成下一轮推荐。所有计算只使用事件发生前的画像，避免未来行为泄漏。",
    )
    policy = report["ranking_policy"]
    add_table(
        doc,
        ["项目", "配置"],
        [
            ["实验周期", "2026年11月12日至18日，共7天"],
            ["用户与候选", f"{report['users']}名用户，{report['candidates']}条候选UGC"],
            ["曝光规模", f"每人每天{report['exposures_per_user_per_day']}次，共{report['total_events']}次"],
            ["随机种子", str(report["seed"])],
            ["排序权重", f"动态兴趣{policy['dynamic_interest']:.0%}，探索{policy['exploration']:.0%}，质量{policy['quality']:.0%}"],
            ["探索机制", "每轮约20%的位置用于探索低画像匹配内容"],
            ["重复曝光", "已曝光内容进入两天冷却期，之后允许再次进入候选"],
            ["兴趣漂移", "user-001第4天转向科技数码；user-004第5天增强旅行户外兴趣"],
        ],
        [4.0, 11.8],
    )

    add_heading(doc, "17.2 模拟行为结果", 2)
    add_body(
        doc,
        "420次曝光中，系统记录了186次正向有效行为、128次负向行为和106次仅曝光。正向行为更新consumer_tag_bag，快速划走和不感兴趣更新negative_tag_bag，仅曝光只记录日志而不改变兴趣权重。",
    )
    event_rows = []
    for event_type, label in EVENT_LABELS.items():
        count = int(report["event_counts"].get(event_type, 0))
        target = "不更新兴趣"
        if event_type in {"click", "dwell", "complete", "like", "save"}:
            target = "消费标签背包"
        elif event_type in {"quick_skip", "not_interested"}:
            target = "负向标签背包"
        event_rows.append([label, str(count), percent(count / report["total_events"]), target])
    add_table(doc, ["行为", "次数", "占比", "更新对象"], event_rows, [3.0, 2.0, 2.2, 8.6])

    add_heading(doc, "17.3 逐日推荐指标", 2)
    add_body(
        doc,
        "离线指标以当天更新前的Top 5推荐为对象。HitRate衡量列表中是否至少出现一条相关内容，Precision衡量相关内容比例，NDCG同时考虑相关性和排序位置。",
    )
    metric_rows = [
        [
            str(day["day"]),
            day["date"],
            percent(day["mean_hit_rate_at_5"]),
            percent(day["mean_precision_at_5"]),
            f"{day['mean_ndcg_at_5']:.3f}",
        ]
        for day in report["daily_results"]
    ]
    add_table(
        doc,
        ["天数", "日期", "HitRate@5", "Precision@5", "NDCG@5"],
        metric_rows,
        [1.8, 3.2, 3.4, 3.7, 3.2],
    )
    day_1, day_6, day_7 = (
        report["daily_results"][0],
        report["daily_results"][5],
        report["daily_results"][6],
    )
    add_body(
        doc,
        f"第1天的NDCG@5为{day_1['mean_ndcg_at_5']:.3f}，随后因候选冷却、探索流量和兴趣漂移而波动。"
        f"第6天降至{day_6['mean_ndcg_at_5']:.3f}，第7天恢复至{day_7['mean_ndcg_at_5']:.3f}。"
        "该变化说明动态画像和探索策略能够重新找到相关内容，但目前尚未与静态画像基线进行同条件对照，因此不能把波动解释为动态方案带来的净提升。",
    )

    add_heading(doc, "17.4 标签背包更新与兴趣漂移", 2)
    add_body(
        doc,
        "实验结束后，6名用户的有效行为数为44至66次，画像阶段均为hot_start。当前规则在20次有效行为后把行为画像权重提高到0.95，因此所有用户在7天内都接近权重上限。这个速度便于验证链路，但上线前需要降低增速并按行为质量加权。",
    )
    final_rows = []
    for user in report["final_users"]:
        tags = "；".join(
            f"{value['category']} {value['weight']:.3f}" for value in user["top_profile"] if value["weight"] > 0
        ) or "暂无正向标签"
        final_rows.append(
            [
                user["user_id"],
                user["stage"],
                str(user["effective_behavior_count"]),
                f"{user['behavior_profile_weight']:.2f}",
                tags,
            ]
        )
    add_table(
        doc,
        ["用户", "阶段", "有效行为", "行为画像权重", "最终主要标签"],
        final_rows,
        [2.3, 2.3, 2.2, 3.0, 6.0],
    )

    add_bold_label(doc, "user-001兴趣漂移结果")
    user_001_rows = []
    for day in report["daily_results"]:
        user = next(value for value in day["users"] if value["user_id"] == "user-001")
        profile = "；".join(
            f"{value['category']} {value['weight']:.3f}"
            for value in user["profile_after_update"]
            if value["weight"] > 0
        )
        user_001_rows.append([str(day["day"]), profile])
    add_table(doc, ["天数", "更新后的主要画像"], user_001_rows, [2.2, 13.6])
    add_body(
        doc,
        "user-001在第4天转向科技数码后，第6天首次形成科技数码行为标签；第7天科技标签权重为0.061，并在重新推荐中升至第1名。与此同时，旅行户外仍保持0.493，说明探索流量已经发现新兴趣，但长期注册兴趣下降较慢。user-004也出现相同现象：最终旅行户外权重为0.170，仍低于交通工具的0.891。",
    )

    add_heading(doc, "17.5 工程验证", 2)
    add_bullet(doc, "420条事件全部成功应用，420个event_id均唯一。")
    add_bullet(doc, "相同event_id重复处理时会被跳过，避免重复累计权重。")
    add_bullet(doc, "正向消费、负向反馈和创作行为分别更新不同标签背包。")
    add_bullet(doc, "推荐和画像更新严格按照事件时间执行，没有使用未来行为。")
    add_bullet(doc, "项目共22项自动测试通过，覆盖正负反馈、幂等性、动态排序和NDCG取值范围。")

    add_heading(doc, "17.6 结论与后续测试", 2)
    add_body(
        doc,
        "本实验完成了热启动最小闭环，证明消费行为和负反馈可以改变标签背包，并影响下一轮排序。当前结果仍属于工程可行性验证：用户反馈由规则模拟，UGC标签来自文本关键词，候选池只有100条，也没有真实曝光偏差和线上反馈。",
    )
    add_body(
        doc,
        "下一轮应同时运行静态注册画像、无衰减累计、当前动态标签背包和提高短期权重四组方案，在相同事件序列上比较NDCG、兴趣适应延迟和负反馈抑制率。还应把行为画像权重的饱和阈值从20次提高，并融合Chinese CLIP图片标签、OCR文字和模型置信度。",
    )

    TMP_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(TMP_PATH)
    os.replace(TMP_PATH, DOCX_PATH)
    print(DOCX_PATH)


if __name__ == "__main__":
    main()
