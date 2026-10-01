"""Build evals/spikes/clause_key/heldout.csv from verbatim public/fixture contract text.

Labels are written here, BEFORE any system run, by meaning (not by what the lexicon can do).
Run from repo root: ai-service/.venv/Scripts/python.exe <this file>
"""
import csv
import html
import json
import pathlib
import re
import sys
from html.parser import HTMLParser

sys.path.insert(0, ".")
from evals.spikes.clause_key.import_heldout import FIELDS  # noqa: E402

W = pathlib.Path(__file__).parent / "web"
FIX = pathlib.Path("ai-service/fixtures/contracts")


class T(HTMLParser):
    def __init__(s):
        super().__init__()
        s.out, s.skip = [], 0

    def handle_starttag(s, t, a):
        if t in ("script", "style", "noscript"):
            s.skip += 1
        if t in ("p", "li", "br", "div", "tr", "h1", "h2", "h3", "h4", "td"):
            s.out.append("\n")

    def handle_endtag(s, t):
        if t in ("script", "style", "noscript") and s.skip:
            s.skip -= 1

    def handle_data(s, d):
        if not s.skip:
            s.out.append(d)


def lines_of(src):
    if src.endswith(".md"):
        txt = (FIX / src).read_text(encoding="utf-8").replace("**", "")
    else:
        t = T()
        t.feed((W / f"{src}.html").read_bytes().decode("utf-8", "ignore"))
        txt = html.unescape("".join(t.out))
    return [re.sub(r"\s+", " ", ln).strip() for ln in txt.split("\n")]


def grab(src, start, end=None):
    """Exact substring of the first line containing `start`, from `start` through `end`."""
    for ln in lines_of(src):
        i = ln.find(start)
        if i >= 0:
            j = len(ln) if end is None else ln.index(end, i) + len(end)
            return ln[i:j].strip()
    raise SystemExit(f"not found in {src}: {start}")


URLS = {
    "p2": "https://luatvantin.com.vn/post/mau-hop-dong-mua-ban-hang-hoa-co-bao-lanh-thanh-toan-eyJpZCI6MjM3M30=",
    "p5": "https://huutoanlogistics.com/mau-hop-dong-thue-nha-xuong/",
    "p10": "https://ltvlaw.com/tin-tuc/thoa-thuan-bao-mat",
    "p14": "https://www.luatsuhopdong.net/2016/09/hop-dong-cung-cap-dich-vu-phan-mem.html",
    "p15": "https://www.luatsuhopdong.net/2016/09/hop-dong-cung-cap-dich-vu-trien-khai-phan-mem.html",
    "p17": "https://homedy.com/news/mau-hop-dong-thue-xuong-thong-dung-nhat-hien-nay-ne6337",
    "p18": "https://luat90.com/hop-dong-bao-mat-thong-tin-nda/",
    "p19": "https://tanhungha.com.vn/mau-hop-dong-mua-ban-may-moc-thiet-bi-chuan-va-day-du-cho-doanh-nghiep-n1701.html",
    "p22": "https://hoiluatsu.vn/mau-hop-dong-cho-thue-mat-bang-kinh-doanh",
    "p23": "https://www.luatsuhopdong.net/2015/10/hop-dong-thue-mat-bang-kinh-doanh.html",
    "p24": "https://thue.man.net.vn/hop-dong-dich-vu-ke-toan-thue/",
    "p26": "https://apolatlegal.com/vi/blog/phat-cham-tien-do-hop-dong-xay-dung/",
    "p27": "https://homedy.com/news/mau-hop-dong-thue-mat-bang-don-gian-day-du-dieu-khoan-phap-ly-ne5427",
    "p28": "https://maudon.net/tai-mau-hop-dong-thue-mat-bang-kinh-doanh",
    "p29": "https://www.kiemtoanxaydung.vn/vi-pham-tre-han-hop-dong-thi-cong-xay-dung/",
    "p30": "https://huynhnamlawfirm.vn/gia-tri-tinh-phat-vi-pham-hop-dong/",
    "HD-TONG-HOP.vi.md": "repo:ai-service/fixtures/contracts/HD-TONG-HOP.vi.md",
    "AI2-TEST-MASTER.body.md": "repo:ai-service/fixtures/contracts/AI2-TEST-MASTER.body.md",
}
SALES_AB = "Bên A=BUYER; Bên B=SELLER"
LEASE_AB = "Bên A=LESSOR; Bên B=LESSEE"
SVC_AB = "Bên A=CUSTOMER; Bên B=SUPPLIER"


def R(b, a, q, anchor, ct, cv="", note=""):
    return dict(frame_type="REMEDY", bearer=b, action=a, qualifier=q, anchor=anchor,
                consequence_type=ct, consequence_value=cv, note=note)


C = [
    ("H01", "SALES", "p2", "Nếu Bên Mua chậm thanh toán theo thời hạn", None, "", [
        R("BUYER", "PAY", "LATE", "thanh toán tiền lãi với lãi suất 0,5%", "INTEREST", "0.5"),
        R("BUYER", "PAY", "LATE", "Bên Mua chịu phạt 8% giá trị Hợp Đồng bị vi phạm", "PENALTY_RATE", "8",
          "trigger also covers late performance of any obligation")]),
    ("H02", "SALES", "p2", "Nếu Bên Mua không tiếp nhận Hàng Hóa", None, "", [
        R("BUYER", "NONE", "", "chịu phạt với mức phạt 0,5%", "PENALTY_RATE", "0.5", "taking delivery: no key"),
        R("BUYER", "NONE", "", "sẽ bị phạt 8% giá trị Hợp Đồng bị vi phạm", "PENALTY_RATE", "8", "taking delivery: no key")]),
    ("H03", "SALES", "p2", "Nếu Bên Bán không thực hiện nghĩa vụ quy định", None, "", [
        R("SELLER", "ANY_OBLIGATION", "NOT_PERFORMED", "Bên Mua có quyền đơn phương chấm dứt Hợp Đồng", "TERMINATION"),
        R("SELLER", "ANY_OBLIGATION", "NOT_PERFORMED", "Bên Bán phải bồi thường các thiệt hại thực tế", "DAMAGES")]),
    ("H04", "SALES", "p2", "Các Bên cam kết thực hiện tất cả", None, "", [
        R("ANY_PARTY", "ANY_OBLIGATION", "NOT_PERFORMED", "sẽ bị phạt 8% phần giá trị", "PENALTY_RATE", "8",
          "trigger: not performing OR unilateral termination"),
        R("ANY_PARTY", "ANY_OBLIGATION", "NOT_PERFORMED", "phải bồi thường toàn bộ những thiệt hại", "DAMAGES")]),
    ("H05", "SALES", "p2", "Trong trường hợp việc thực hiện hợp đồng của một bên bị chậm trễ", None, "", [
        R("ANY_PARTY", "ANY_OBLIGATION", "LATE", "có quyền đơn phương chấm dứt hợp đồng", "TERMINATION", "", "force-majeure delay")]),
    ("H06", "LEASE", "p5", "Trong trường hợp một bên vi phạm hợp đồng hoặc đơn phương", None, "", [
        R("ANY_PARTY", "ANY_OBLIGATION", "", "bồi thường cho bên kia một khoản tiền tương đương với 02 tháng tiền thuê",
          "DAMAGES", "", "trigger: breach OR unilateral termination")]),
    ("H07", "LEASE", "p17", "Trường hợp Bên B không thanh toán đủ, đúng thời hạn tiền thuê", None, LEASE_AB, [
        R("LESSEE", "PAY", "LATE", "phải chịu lãi suất chậm trả", "INTEREST")]),
    ("H08", "LEASE", "p23", "Trong trường hợp bên B chậm trả tiền thuê mặt bằng sau 30 ngày", None, LEASE_AB, [
        R("LESSEE", "PAY", "LATE", "Bên A được quyền đơn phương chấm dứt Hợp đồng", "TERMINATION")]),
    ("H09", "LEASE", "p27", "Nếu bên B chậm trả tiền thuê mặt bằng trong thời gian 01 tháng", None, LEASE_AB, [
        R("LESSEE", "PAY", "LATE", "bên A có quyền đơn phương chấm dứt hợp đồng", "TERMINATION")]),
    ("H10", "LEASE", "p27", "Tiền thuê nhà sẽ được thanh toán từ ngày", None, LEASE_AB, [
        R("LESSEE", "PAY", "LATE", "sẽ tính theo lãi suất tiền gửi tiết kiệm", "INTEREST")]),
    ("H11", "LEASE", "p28", "Trong trường hợp bên thuê trả tài sản thuê muộn", "thời gian trễ;", "", [
        R("LESSEE", "RETURN_ASSET", "LATE", "phải bồi thường thiệt hại", "DAMAGES")]),
    ("H12", "LEASE", "p28", "Nếu bên thuê không trả tiền trong ba kỳ liên tiếp", "không cần thông báo trước", "", [
        R("LESSEE", "PAY", "NOT_PERFORMED", "bên cho thuê có quyền chấm dứt hợp đồng", "TERMINATION")]),
    ("H13", "SALES", "p19", "Nếu bên B giao hàng chậm hơn thời hạn giao hàng quá 10 ngày", None, SALES_AB, [
        R("SELLER", "DELIVER", "LATE", "bên A có quyền đơn phương chấm dứt hợp đồng", "TERMINATION"),
        R("SELLER", "DELIVER", "LATE", "phải chịu một khoản tiền phạt do vi phạm hợp đồng là 50 triệu đồng",
          "PENALTY_FIXED", "50000000")]),
    ("H14", "SALES", "p19", "Nếu bên A thanh toán chậm thì phải chịu thêm lãi suất", None, SALES_AB, [
        R("BUYER", "PAY", "LATE", "phải chịu thêm lãi suất cho thời gian chậm thanh toán là 2%/tháng", "INTEREST", "2")]),
    ("H15", "SALES", "p30", "Trong trường hợp Bên B không giao hàng theo đúng thời hạn đã quy định", "Hợp đồng.", SALES_AB, [
        R("SELLER", "DELIVER", "LATE", "sẽ chịu phạt với mức phạt 1%/ngày", "PENALTY_RATE", "1")]),
    ("H16", "SUPPLY_SERVICE", "p15", "5.4. Trong trường hợp Bên A thanh toán cho Bên B chậm", None, SVC_AB, [
        R("CUSTOMER", "PAY", "LATE", "Bên A chịu phạt theo mức lãi suất bằng 150% lãi suất cơ bản", "INTEREST")]),
    ("H17", "SUPPLY_SERVICE", "p14", "11.5. Các bên xác nhận và đồng ý", None, SVC_AB, [
        R("ANY_PARTY", "ANY_OBLIGATION", "", "chịu phạt vi phạm với mức 8%", "PENALTY_RATE", "8"),
        R("ANY_PARTY", "ANY_OBLIGATION", "", "bồi thường cho bên kia toàn bộ thiệt hại", "DAMAGES")]),
    ("H18", "SUPPLY_SERVICE", "p14", "11.4. Bên vi phạm dẫn đến việc chấm dứt", None, SVC_AB, [
        R("ANY_PARTY", "ANY_OBLIGATION", "", "phải bồi thường cho bên kia toàn bộ thiệt hại", "DAMAGES")]),
    ("H19", "SUPPLY_SERVICE", "p14", "4.1. Bên B bảo đảm là chủ sở hữu hợp pháp", None, SVC_AB, [
        R("SUPPLIER", "NONE", "", "phải bồi thường mọi thiệt hại gây ra cho Bên A", "DAMAGES", "", "IP infringement: no key")]),
    ("H20", "NDA", "p10", "5.1. Bên vi phạm nghĩa vụ bảo mật", None, "", [
        R("ANY_PARTY", "DISCLOSE", "UNAUTHORIZED", "bồi thường toàn bộ thiệt hại thực tế", "DAMAGES", "", "breach of confidentiality")]),
    ("H21", "NDA", "p10", "5.2. Ngoài bồi thường thiệt hại", None, "", [
        R("ANY_PARTY", "DISCLOSE", "UNAUTHORIZED", "còn phải chịu phạt vi phạm số tiền", "PENALTY_FIXED", "",
          "breached obligation implicit (confidentiality article)")]),
    ("H22", "NDA", "p18", "Hậu Quả Vi Phạm: Bên nhận thừa nhận", None, "Bên A=DISCLOSER", [
        R("RECIPIENT", "DISCLOSE", "UNAUTHORIZED", "Bên A có quyền yêu cầu bồi thường thiệt hại", "DAMAGES")]),
    ("H23", "SUPPLY_SERVICE", "p24", "5.1. Bên B cam kết bồi thường 100%", None, SVC_AB, [
        R("SUPPLIER", "PROVIDE_SERVICE", "DEFECTIVE", "cam kết bồi thường 100%", "DAMAGES", "100", "service errors by B's staff")]),
    ("H24", "SUPPLY_SERVICE", "AI2-TEST-MASTER.body.md", "Chậm giao thiết bị bị phạt", None, "", [
        R("SUPPLIER", "DELIVER", "LATE", "bị phạt 0,2% giá trị phần chậm giao", "PENALTY_RATE", "0.2", "bearer implicit (Bên B)")]),
    ("H25", "SUPPLY_SERVICE", "AI2-TEST-MASTER.body.md", "Chậm khắc phục lỗi phần cứng", None, "", [
        R("SUPPLIER", "WARRANT", "LATE", "bị phạt 0,1% giá trị phần lỗi", "PENALTY_RATE", "0.1", "bearer implicit (Bên B)")]),
    ("H26", "CONSTRUCTION_WORK", "HD-TONG-HOP.vi.md", "5.1. Phạt chậm tiến độ chung", None, "", [
        R("CONTRACTOR", "COMPLETE_WORK", "LATE", "0,2% (hai phần nghìn)/ngày", "PENALTY_RATE", "0.2", "bearer implicit (Bên B)")]),
    ("H27", "CONSTRUCTION_WORK", "HD-TONG-HOP.vi.md", "5.2. Phạt chậm phần xây lắp", None, "", [
        R("CONTRACTOR", "COMPLETE_WORK", "LATE", "0,1%/ngày trên giá trị phần xây lắp chậm", "PENALTY_RATE", "0.1", "scope: xây lắp")]),
    ("H28", "CONSTRUCTION_WORK", "HD-TONG-HOP.vi.md", "5.3. Phạt chậm phần thiết bị", None, "", [
        R("CONTRACTOR", "COMPLETE_WORK", "LATE", "0,05%/ngày trên giá trị phần thiết bị chậm", "PENALTY_RATE", "0.05", "scope: thiết bị")]),
    ("H30", "CONSTRUCTION_WORK", "HD-TONG-HOP.vi.md", "9.10. Thời hạn thanh toán không kéo dài vô hạn", None, "", [
        R("OWNER", "PAY", "LATE", "chậm thanh toán phát sinh lãi", "INTEREST", "", "bearer implicit (Bên A)")]),
    ("H31", "CONSTRUCTION_WORK", "HD-TONG-HOP.vi.md", "4.3. Chỉ huy trưởng công trường", None, "Bên A=OWNER; Bên B=CONTRACTOR", [
        R("CONTRACTOR", "NONE", "", "Bên A được tạm dừng điểm thi công liên quan", "SUSPENSION", "", "site manager absence: no key")]),
    ("H32", "CONSTRUCTION_WORK", "p29", "Đối với Bên nhận thầu: nếu chậm tiến độ", None, "", [
        R("CONTRACTOR", "COMPLETE_WORK", "LATE", "thì phạt… % giá hợp đồng", "PENALTY_RATE", "", "template with blanks")]),
    ("H33", "CONSTRUCTION_WORK", "p26", "Bên giao thầu phải bồi thường cho bên nhận thầu trong trường do", None, "", [
        R("OWNER", "ANY_OBLIGATION", "", "Bên giao thầu phải bồi thường cho bên nhận thầu", "DAMAGES", "", "owner-caused disruption/delay")]),
    ("H34", "LEASE", "p17", "a) Bất kỳ Bên nào vi phạm nghĩa vụ", None, "", [
        R("ANY_PARTY", "ANY_OBLIGATION", "", "thì phải bồi thường thiệt hại", "DAMAGES")]),
    ("H35", "LEASE", "p17", "6.3. Trường hợp một trong hai Bên vi phạm nghiêm trọng", None, "", [
        R("ANY_PARTY", "ANY_OBLIGATION", "", "có quyền đơn phương chấm dứt thực hiện hợp đồng", "TERMINATION"),
        R("ANY_PARTY", "ANY_OBLIGATION", "", "yêu cầu bồi thường thiệt hại", "DAMAGES")]),
    ("H36", "LEASE", "p22", "Bên B có quyền đơn phương chấm dứt hợp đồng trong trường hợp Bên A vi phạm", None, LEASE_AB, [
        R("LESSOR", "ANY_OBLIGATION", "", "Bên B có quyền đơn phương chấm dứt hợp đồng", "TERMINATION")]),
]


def main():
    rows, sources = [], {}
    for cid, prof, src, start, end, parties, frames in C:
        text = grab(src, start, end).lstrip("-–• ").strip("“”\" ")
        sources[cid] = URLS[src]
        for k, f in enumerate(frames):
            assert f["anchor"] in text, (cid, f["anchor"], text)
            rows.append({"clause_id": cid, "profile": prof if k == 0 else "", "text": text if k == 0 else "",
                         "context_parties": parties if k == 0 else "", **f})
    # H29: graduated bullet list (HD-TONG-HOP 5.4) spans three lines; join them
    lines = lines_of("HD-TONG-HOP.vi.md")
    i = next(n for n, ln in enumerate(lines) if ln.startswith("5.4. Bậc thang"))
    t29 = " ".join(lines[i:i + 3]).replace("- ", "")
    sources["H29"] = URLS["HD-TONG-HOP.vi.md"]
    for k, (anc, val) in enumerate([("dưới 10 ngày chậm: 0,05%/ngày", "0.05"), ("từ 10 ngày trở lên: 0,1%/ngày", "0.1")]):
        assert anc in t29, (anc, t29)
        rows.append({"clause_id": "H29", "profile": "CONSTRUCTION_WORK" if k == 0 else "", "text": t29 if k == 0 else "",
                     "context_parties": "", **R("CONTRACTOR", "COMPLETE_WORK", "LATE", anc, "PENALTY_RATE", val,
                                                "graduated, bearer implicit")})
    out = pathlib.Path("evals/spikes/clause_key/heldout.csv")
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    pathlib.Path("evals/spikes/clause_key/heldout_sources.json").write_text(
        json.dumps(sources, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len({r["clause_id"] for r in rows}), "clauses,", len(rows), "frames")
    for r in rows:
        if r["text"]:
            print(f"{r['clause_id']}: {r['text'][:170]}")


if __name__ == "__main__":
    main()
