"""システム構成図とフロー図を生成する（docs/figures/ へPNG出力）。"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon
from pathlib import Path

FONT = str(Path.home() / "fonts" / "NotoSansJP-Regular.otf")
try:
    Path(FONT).read_bytes()[:2]
except Exception:
    FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
font_manager.fontManager.addfont(FONT)
plt.rcParams["font.family"] = font_manager.FontProperties(fname=FONT).get_name()

OUT = Path(__file__).resolve().parent.parent / "docs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

C_MAIN = "#DCE9F7"; C_SUB = "#F2F2F2"; C_ACCENT = "#FCE8D5"; C_PRIV = "#F8D7DA"


def box(ax, x, y, w, h, text, fc=C_MAIN, fs=10, bold=False, ec="#404040"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                                fc=fc, ec=ec, lw=1.1))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", linespacing=1.5)


def arrow(ax, p1, p2, text="", fs=8.5, style="-", rad=0.0, tpos=0.5, tdy=0.14):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="->", mutation_scale=13,
                                 linestyle=style, lw=1.1, color="#404040",
                                 connectionstyle=f"arc3,rad={rad}"))
    if text:
        mx = p1[0] + (p2[0] - p1[0]) * tpos
        my = p1[1] + (p2[1] - p1[1]) * tpos
        ax.text(mx, my + tdy, text, ha="center", va="bottom", fontsize=fs,
                bbox=dict(fc="white", ec="none", pad=0.6))


def finish(fig, name):
    fig.savefig(OUT / name, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", name)


# ---------- システム構成図 ----------
fig, ax = plt.subplots(figsize=(10.5, 5.6))
ax.set_xlim(0, 10.5); ax.set_ylim(0, 5.6); ax.axis("off")
ax.text(5.25, 5.38, "システム構成図 ― 個人用ナレッジRAG", ha="center", fontsize=13, fontweight="bold")

box(ax, 0.2, 3.3, 1.8, 1.1, "利用者\n（本人）", C_SUB, 10, True)
box(ax, 0.2, 1.2, 1.8, 1.1, "GitHub公開リポ\n道具・設計文書・\n架空サンプル・数字", C_SUB, 9)
box(ax, 2.9, 3.3, 2.4, 1.1, "ネロ（Muse）\n質問し、出典を見て\n答えを作る", C_ACCENT, 10, True)
box(ax, 2.9, 1.2, 2.4, 1.1, "公開の範囲\n実データは出さない", C_SUB, 9)

box(ax, 6.2, 2.2, 2.1, 2.2, "ragcli（検索コア）\n\ningest：取り込み\nsearch：検索\neval：評価", C_MAIN, 10, True)
box(ax, 6.2, 0.5, 2.1, 1.1, "MCPサーバー\n（第2段階で同じ\n検索コアを公開）", C_SUB, 9)

box(ax, 8.9, 3.3, 1.5, 1.1, "文書フォルダ\n実物の運用知識\n（非公開）", C_PRIV, 9, True)
box(ax, 8.9, 1.2, 1.5, 1.1, "索引\nベクトル＋\nチャンク情報\n（非公開）", C_PRIV, 9, True)

arrow(ax, (2.0, 3.95), (2.9, 3.95), "質問", tdy=0.1)
arrow(ax, (2.9, 3.6), (2.0, 3.6), "出典つきの答え", tdy=-0.32)
arrow(ax, (5.3, 3.95), (6.2, 3.95), "検索を呼ぶ", fs=8, tdy=0.1)
arrow(ax, (6.2, 3.6), (5.3, 3.6), "出典つきチャンク", fs=8, tdy=-0.32)
arrow(ax, (7.25, 2.2), (7.25, 1.6), "", style="--")
arrow(ax, (8.9, 3.95), (8.3, 3.95), "取り込み対象", fs=8, tdy=0.1)
arrow(ax, (8.3, 2.6), (8.9, 1.95), "読み書き", fs=8, tpos=0.35, tdy=0.12)
arrow(ax, (6.2, 1.6), (5.3, 1.6), "同じコードと設計", fs=8, style="--", tdy=0.1)
arrow(ax, (2.9, 1.6), (2.0, 1.6), "公開する", fs=8, style="--", tdy=0.1)
ax.text(5.25, 0.08, "実物の文書と索引は公開しない。公開するのは道具・設計・架空サンプル・集計した数字だけ。",
        ha="center", fontsize=9, style="italic")
finish(fig, "system_architecture.png")

# ---------- 取り込みフロー図 ----------
fig, ax = plt.subplots(figsize=(7.6, 8.6))
ax.set_xlim(0, 7.6); ax.set_ylim(0, 8.6); ax.axis("off")
ax.text(3.8, 8.38, "処理フロー図 ― 取り込み（ingest）", ha="center", fontsize=12.5, fontweight="bold")


def flow_box(y, text, fc=C_MAIN, h=0.62, fs=9.5):
    box(ax, 2.0, y, 3.6, h, text, fc, fs)


def diamond(cx, cy, text, fs=9):
    pts = [(cx, cy + 0.52), (cx + 1.55, cy), (cx, cy - 0.52), (cx - 1.55, cy)]
    ax.add_patch(Polygon(pts, closed=True, fc=C_ACCENT, ec="#404040", lw=1.1))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs, linespacing=1.4)


flow_box(7.5, "開始：対象フォルダを走査する", C_SUB)
arrow(ax, (3.8, 7.5), (3.8, 7.22))
flow_box(6.6, "ファイルごとに内容ハッシュを比べる", C_MAIN)
arrow(ax, (3.8, 6.6), (3.8, 6.28))
diamond(3.8, 5.76, "前回から\n変わったか")
arrow(ax, (3.8, 5.24), (3.8, 4.98), "はい")
flow_box(4.36, "読み取り：見出しつき段落にする", C_MAIN)
arrow(ax, (3.8, 4.36), (3.8, 4.08))
flow_box(3.46, "分割：見出し単位＋長さ上限で切る", C_MAIN)
arrow(ax, (3.8, 3.46), (3.8, 3.18))
flow_box(2.56, "埋め込み：チャンクをベクトル化する", C_MAIN)
arrow(ax, (3.8, 2.56), (3.8, 2.28))
flow_box(1.66, "索引へ保存（消えた文書は除く）", C_MAIN)
arrow(ax, (3.8, 1.66), (3.8, 1.38))
flow_box(0.76, "完了：件数の報告をJSONで返す", C_SUB)
ax.add_patch(FancyArrowPatch((5.35, 5.76), (6.9, 5.76), arrowstyle="-", lw=1.1, color="#404040"))
ax.add_patch(FancyArrowPatch((6.9, 5.76), (6.9, 1.97), arrowstyle="-", lw=1.1, color="#404040"))
ax.add_patch(FancyArrowPatch((6.9, 1.97), (5.6, 1.97), arrowstyle="->", mutation_scale=13, lw=1.1, color="#404040"))
ax.text(6.15, 5.9, "いいえ：そのまま使う", fontsize=9, ha="center")
ax.text(6.9, 3.8, "読めないファイルは\n警告に残し、全体は続ける", fontsize=8.5, ha="center",
        bbox=dict(fc="#FFF7E6", ec="#D9A441", pad=3))
finish(fig, "flow_ingest.png")

# ---------- 検索フロー図 ----------
fig, ax = plt.subplots(figsize=(7.6, 8.2))
ax.set_xlim(0, 7.6); ax.set_ylim(0, 8.2); ax.axis("off")
ax.text(3.8, 7.98, "処理フロー図 ― 検索（search）", ha="center", fontsize=12.5, fontweight="bold")

flow_box(7.1, "質問を受け取る", C_SUB)
arrow(ax, (3.8, 7.1), (3.8, 6.82))
box(ax, 0.5, 5.9, 3.1, 0.92, "キーワード検索\n（BM25）で順位を出す", C_MAIN, 9.5)
box(ax, 4.0, 5.9, 3.1, 0.92, "ベクトル検索\n（意味の近さ）で順位を出す", C_MAIN, 9.5)
ax.add_patch(FancyArrowPatch((3.0, 6.82), (2.05, 6.82), arrowstyle="->", mutation_scale=13, lw=1.1, color="#404040"))
ax.add_patch(FancyArrowPatch((4.6, 6.82), (5.55, 6.82), arrowstyle="->", mutation_scale=13, lw=1.1, color="#404040"))
arrow(ax, (2.05, 5.9), (3.0, 5.35))
arrow(ax, (5.55, 5.9), (4.6, 5.35))
flow_box(4.55, "順位を統合し、関連度を0〜1にする", C_MAIN, h=0.8)
arrow(ax, (3.8, 4.55), (3.8, 4.23))
diamond(3.8, 3.71, "最上位の関連度が\n閾値以上か")
arrow(ax, (3.8, 3.19), (3.8, 2.93), "はい")
flow_box(2.31, "候補あり：出典つきで上位を返す", C_MAIN)
arrow(ax, (3.8, 2.31), (3.8, 2.03))
flow_box(1.41, "完了：JSON（または簡易表示）で返す", C_SUB)
ax.add_patch(FancyArrowPatch((5.35, 3.71), (6.9, 3.71), arrowstyle="-", lw=1.1, color="#404040"))
ax.add_patch(FancyArrowPatch((6.9, 3.71), (6.9, 1.72), arrowstyle="-", lw=1.1, color="#404040"))
ax.add_patch(FancyArrowPatch((6.9, 1.72), (5.6, 1.72), arrowstyle="->", mutation_scale=13, lw=1.1, color="#404040"))
ax.text(6.2, 3.85, "いいえ", fontsize=9, ha="center")
ax.text(6.9, 2.7, "候補なしとして返す\n（無理に答えを作らない）", fontsize=8.5, ha="center",
        bbox=dict(fc="#FFF7E6", ec="#D9A441", pad=3))
finish(fig, "flow_search.png")
