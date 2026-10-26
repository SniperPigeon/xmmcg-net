"""
互评评分汇总导出工具

提供可复用的核心函数，供 admin action 和独立脚本调用。

生成包含两个工作表的 xlsx：
  - 「评分」    ：每位评分人一列，显示其给每张谱面的分数
  - 「评分与评语」：每位评分人两列（评分 + 评语），相邻放置
两表均只包含已投稿的完整谱面，不包含归档的旧半成品。
"""

import io
from collections import defaultdict
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .models import Chart, PeerReview

# 样式常量
_FILL_TITLE = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
_FILL_HEADER = PatternFill(start_color="BDD7EE", end_color="BDD7EE", fill_type="solid")
_FILL_SUBHDR = PatternFill(start_color="DEEAF1", end_color="DEEAF1", fill_type="solid")
_FILL_ROW_ODD = PatternFill(fill_type=None)
_FILL_ROW_EVEN = PatternFill(
    start_color="F2F2F2", end_color="F2F2F2", fill_type="solid"
)

_FONT_TITLE = Font(bold=True, size=13, color="FFFFFF")
_FONT_HEADER = Font(bold=True, size=10)
_ALIGN_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
_ALIGN_LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)


# ---------------------------------------------------------------------------
# 公开接口
# ---------------------------------------------------------------------------


def safe_cell(value):
    # 文本保持原样显示，避免被 Excel 当作公式执行。
    return (
        "'" + value
        if isinstance(value, str) and value.startswith(("=", "+", "-", "@"))
        else value
    )


def export_peer_review_scores(chart_ids=None) -> bytes:
    """保留原有中文双工作表、列分组、格式、排序及署名优先级。"""
    charts_qs = (
        Chart.objects.select_related("user", "user__profile")
        .filter(status="submitted")
        .order_by("id")
    )
    if chart_ids is not None:
        charts_qs = charts_qs.filter(id__in=chart_ids)
    charts = list(charts_qs)
    records = (
        PeerReview.objects.filter(chart_id__in=[chart.pk for chart in charts])
        .order_by("chart_id", "reviewer__username", "created_at", "id")
        .values("chart_id", "reviewer__username", "score", "comment", "favorite")
    )
    chart_reviews = defaultdict(dict)
    reviewer_names = set()
    for review in records:
        name = review["reviewer__username"]
        chart_reviews[review["chart_id"]][name] = review
        reviewer_names.add(name)
    reviewers = sorted(reviewer_names)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "评分"
    _build_scores_sheet(sheet, charts, chart_reviews, reviewers, "")
    sheet = workbook.create_sheet(title="评分与评语")
    _build_scores_comments_sheet(sheet, charts, chart_reviews, reviewers, "")
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------

_META_COLS = ["谱面ID", "歌曲名", "谱师"]  # 固定的左侧列
_N_META = len(_META_COLS)


def _style_title_row(ws, row_idx: int, total_cols: int, text: str):
    """合并第 row_idx 行所有列并应用标题样式。"""
    ws.merge_cells(
        start_row=row_idx,
        start_column=1,
        end_row=row_idx,
        end_column=total_cols,
    )
    cell = ws.cell(row=row_idx, column=1, value=text)
    cell.font = _FONT_TITLE
    cell.fill = _FILL_TITLE
    cell.alignment = _ALIGN_CENTER
    ws.row_dimensions[row_idx].height = 22


def _style_header_cell(cell, fill=None):
    cell.font = _FONT_HEADER
    cell.fill = fill or _FILL_HEADER
    cell.alignment = _ALIGN_CENTER


def _preferred_name(user, fallback: str) -> str:
    """优先返回 UserProfile.preferred_name，不存在时用 fallback。"""
    try:
        pn = user.profile.preferred_name
        if pn:
            return pn
    except Exception:
        pass
    return fallback


def trimmed_mean(scores: list) -> float | None:
    """去掉最高分和最低分后的平均值（各去一个）。
    - n >= 3：去一高一低后平均，保留两位小数
    - n == 2：直接平均两分
    - n <= 1：原值或 None
    """
    valid = [Decimal(str(s)) for s in scores if s is not None]
    if not valid:
        return None
    if len(valid) <= 2:
        return round(sum(valid) / len(valid), 2)
    trimmed = sorted(valid)[1:-1]
    return round(sum(trimmed) / len(trimmed), 2)


def _meta_row_data(chart) -> list:
    # 与原导出一致：优先资料中的谱师名义，未设置时使用用户名。
    name = _preferred_name(chart.user, chart.user.username)
    return [chart.id, safe_cell(chart.title), safe_cell(name)]


# --- Sheet 1：纯评分 ---


def _build_scores_sheet(ws, charts, chart_reviews, reviewers, title_suffix):
    """
    结构：
      行1：标题（合并）
      行2：谱面ID | 歌曲名 | 谱师名 | reviewer1 | reviewer2 | … | 真爱票数
      行3+：数据
    """
    total_cols = _N_META + len(reviewers) + 2  # +1 去高低均分 +1 真爱票数

    # 标题行
    _style_title_row(ws, 1, total_cols, f"互评评分表{title_suffix}")

    # 列头行
    header = (
        _META_COLS
        + [safe_cell(name) for name in reviewers]
        + ["去高低均分", "真爱票数"]
    )
    ws.append(header)
    for col_idx, cell in enumerate(ws[2], start=1):
        _style_header_cell(cell)

    # 数据行
    for data_row_idx, chart in enumerate(charts, start=1):
        rv = chart_reviews[chart.id]
        scores = [rv[u]["score"] if u in rv else None for u in reviewers]
        trimmed = trimmed_mean(scores)
        fav_count = sum(1 for u in rv.values() if u["favorite"])
        row = _meta_row_data(chart) + scores + [trimmed, fav_count]
        ws.append(row)
        # 隔行底色
        if data_row_idx % 2 == 0:
            for cell in ws[2 + data_row_idx]:
                cell.fill = _FILL_ROW_EVEN

    # 列宽
    col_widths = [8, 28, 16] + [12] * len(reviewers) + [12, 10]
    _set_col_widths(ws, col_widths)

    # 冻结前两行和前三列
    ws.freeze_panes = ws.cell(row=3, column=_N_META + 1)


# --- Sheet 2：评分 + 评语 ---


def _build_scores_comments_sheet(ws, charts, chart_reviews, reviewers, title_suffix):
    """
    结构：
      行1：标题（合并）
      行2：谱面ID | 歌曲名 | 谱师名 | ← reviewer1 (合并2列) → | ← reviewer2 → | … | 真爱票数
      行3：(空) | (空) | (空) | 评分 | 评语 | 评分 | 评语 | … | (空)
      行4+：数据
    """
    n_rv = len(reviewers)
    total_cols = _N_META + n_rv * 2 + 2  # 每人占2列 + 去高低均分 + 真爱票数

    # 标题行
    _style_title_row(ws, 1, total_cols, f"互评评分与评语表{title_suffix}")

    # 第2行：合并每位评分人的双列，写入用户名
    ws.append([""] * total_cols)  # 占一行
    # 固定元信息列表头
    for col_idx, label in enumerate(_META_COLS, start=1):
        cell = ws.cell(row=2, column=col_idx, value=label)
        _style_header_cell(cell)
    # 合并每位评分人占的两列
    for rv_idx, uname in enumerate(reviewers):
        col_start = _N_META + rv_idx * 2 + 1
        col_end = col_start + 1
        ws.merge_cells(
            start_row=2, start_column=col_start, end_row=2, end_column=col_end
        )
        cell = ws.cell(row=2, column=col_start, value=safe_cell(uname))
        _style_header_cell(cell)
    # 去高低均分列头（跨行2-3合并）
    trimmed_col = _N_META + n_rv * 2 + 1
    ws.merge_cells(
        start_row=2, start_column=trimmed_col, end_row=3, end_column=trimmed_col
    )
    cell = ws.cell(row=2, column=trimmed_col, value="去高低均分")
    _style_header_cell(cell)
    # 真爱票数列头（跨行2-3合并）
    fav_col = _N_META + n_rv * 2 + 2
    ws.merge_cells(start_row=2, start_column=fav_col, end_row=3, end_column=fav_col)
    cell = ws.cell(row=2, column=fav_col, value="真爱票数")
    _style_header_cell(cell)
    ws.row_dimensions[2].height = 18

    # 第3行：评分 / 评语 子表头
    subheader = [""] * _N_META
    for _ in reviewers:
        subheader += ["评分", "评语"]
    subheader += ["", ""]  # 去高低均分和真爱票数已合并
    ws.append(subheader)
    for col_idx, cell in enumerate(ws[3], start=1):
        if cell.value:
            _style_header_cell(cell, fill=_FILL_SUBHDR)
        else:
            cell.fill = _FILL_SUBHDR
    ws.row_dimensions[3].height = 16

    # 数据行（从第4行起）
    for data_row_idx, chart in enumerate(charts, start=1):
        rv = chart_reviews[chart.id]
        interleaved = []
        for uname in reviewers:
            if uname in rv:
                interleaved.append(rv[uname]["score"])
                interleaved.append(safe_cell(rv[uname]["comment"] or ""))
            else:
                interleaved += [None, None]
        scores_only = [rv[u]["score"] if u in rv else None for u in reviewers]
        trimmed = trimmed_mean(scores_only)
        fav_count = sum(1 for u in rv.values() if u["favorite"])
        row = _meta_row_data(chart) + interleaved + [trimmed, fav_count]
        ws.append(row)
        if data_row_idx % 2 == 0:
            for cell in ws[3 + data_row_idx]:
                cell.fill = _FILL_ROW_EVEN

    # 列宽
    col_widths = [8, 28, 16]
    for _ in reviewers:
        col_widths += [10, 32]
    col_widths += [12, 10]
    _set_col_widths(ws, col_widths)

    # 冻结前3行和前3列
    ws.freeze_panes = ws.cell(row=4, column=_N_META + 1)


def _set_col_widths(ws, widths: list[int]):
    for col_idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width
