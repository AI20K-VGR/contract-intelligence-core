"""Held-out 2: labelled BEFORE v2 development; the system is not run on it until v2 is frozen.

Run from repo root.
"""
import csv
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, ".")
from build_heldout import R, grab

from evals.spikes.clause_key.import_heldout import FIELDS

URLS = {
    "q43": "https://dichvuketoannhanh.com/mau-hop-dong-thi-cong-nha-o-dan-dung",
    "q44": "https://xaydunghungphu.com/dich-vu/mau-hop-dong-xay-dung-hien-nay-27.html",
    "q46": "https://vanluat.vn/hop-dong-thi-cong-xay-dung-cong-trinh-nha-o.html",
    "q47": "https://luattritam.com.vn/tu-van-soan-thao-hop-dong/dieu-khoan-phat-vi-pham-trong-hop-dong.htm",
    "q49": "https://tktclean.com/mau-hop-dong-dich-vu-ve-sinh-van-phong/",
    "q50": "https://vantaihoangminh.com/hop-dong-van-chuyen-hang-hoa/",
    "q51": "https://meg.vn/mau-hop-dong-dich-vu-ve-sinh-sau-xay-dung/",
    "q52": "https://luatthaian.vn/hop-dong/mau-hop-dong-van-chuyen-hang-hoa/",
    "q53": "https://www.cis.vn/mau-hop-dong-dich-vu-van-chuyen-hang-hoa/",
    "q54": "https://bbiac.com/van-ban-mau/mau-hop-dong-cung-cap-dich-vu-bao-ve/",
    "q55": "https://bigbosslaw.com/hop-dong-dich-vu-bao-tri/",
    "q57": "https://vantaitinphat.vn/hop-dong-thue-xe-tai/",
    "q58": "https://eimskip.vn/mau-hop-dong-thue-kho-bai-chuan",
}
OWN = "Bên A=OWNER; Bên B=CONTRACTOR"
SVC = "Bên A=CUSTOMER; Bên B=SUPPLIER"
LSE = "Bên A=LESSOR; Bên B=LESSEE"
# Convention: loss/damage caused by the provider's staff while performing the
# service = (SUPPLIER, PROVIDE_SERVICE, DEFECTIVE).
C = [
    ("K01", "CONSTRUCTION_WORK", "q43", "Nếu Bên A chậm thanh toán cho Bên B, cụ thể là quá bảy", None, OWN, [
        R("OWNER", "PAY", "LATE", "Bên B có quyền đơn phương chấm dứt hợp đồng thi công", "TERMINATION")]),
    ("K02", "CONSTRUCTION_WORK", "q43", "Bên B có quyền chấm dứt hợp đồng nếu Bên A vi phạm nghĩa vụ thanh toán", None, OWN, [
        R("OWNER", "PAY", "", "Bên B có quyền chấm dứt hợp đồng", "TERMINATION")]),
    ("K03", "CONSTRUCTION_WORK", "q44", "Nếu bên B thi công không kịp tiến độ", None, OWN, [
        R("CONTRACTOR", "COMPLETE_WORK", "LATE", "bên A sẽ phạt 5.000.000", "PENALTY_FIXED", "5000000"),
        R("CONTRACTOR", "COMPLETE_WORK", "LATE", "bên A sẽ thanh lý hợp hợp đồng", "TERMINATION"),
        R("CONTRACTOR", "COMPLETE_WORK", "LATE", "bên B sẽ bồi thường hợp đồng cho bên A", "DAMAGES", "10000000")]),
    ("K04", "CONSTRUCTION_WORK", "q44", "6.1 Bên B có trách nhiệm thi công đúng các chủng loại vật tư", None, OWN, [
        R("CONTRACTOR", "COMPLETE_WORK", "DEFECTIVE", "bên B phải bồi thường cho bên A 10.000.000đ", "DAMAGES", "10000000")]),
    ("K05", "CONSTRUCTION_WORK", "q44", "Nếu một Bên vi phạm hợp đồng, gây thiệt hại cho Bên kia", None, OWN, [
        R("ANY_PARTY", "ANY_OBLIGATION", "", "phải chịu bồi thường hoàn toàn thiệt hại", "DAMAGES"),
        R("ANY_PARTY", "ANY_OBLIGATION", "", "bị phạt vi phạm hợp đồng theo pháp luật hiện hành", "PENALTY_FIXED")]),
    ("K06", "CONSTRUCTION_WORK", "q46", "Trong quá trình thực hiện hợp đồng, nếu xét thấy bên B không đảm bảo", None, OWN, [
        R("CONTRACTOR", "NONE", "", "bên A có quyền đình chỉ và huỷ bỏ hợp đồng", "TERMINATION", "", "capability: no key"),
        R("CONTRACTOR", "COMPLETE_WORK", "DEFECTIVE", "bên B phải bồi thường thiệt hại hư hỏng", "DAMAGES")]),
    ("K07", "SALES", "q47", "Nếu bên bán vi phạm về chất lượng hàng hóa", "số tiền chậm trả", "", [
        R("SELLER", "DELIVER", "DEFECTIVE", "sẽ bị phạt 6% giá trị hàng hóa không đúng chất lượng", "PENALTY_RATE", "6"),
        R("BUYER", "PAY", "LATE", "sẽ bị phạt 5% của số tiền chậm trả", "PENALTY_RATE", "5")]),
    ("K08", "SUPPLY_SERVICE", "q50", "Trong trường hợp chậm thanh toán quá", None, SVC, [
        R("CUSTOMER", "PAY", "LATE", "Bên A sẽ phải chịu lãi suất", "INTEREST")]),
    ("K09", "SUPPLY_SERVICE", "q50", "Hàng gửi bị mất hoặc hư hại hoàn toàn", None, SVC, [
        R("SUPPLIER", "PROVIDE_SERVICE", "DEFECTIVE", "Bồi thường ….% giá trị hàng hóa mất mát", "DAMAGES", "", "carrier loses goods")]),
    ("K10", "SUPPLY_SERVICE", "q51", "8.2. Trường hợp bên A vi phạm nghiêm trọng nghĩa vụ", None, SVC, [
        R("CUSTOMER", "ANY_OBLIGATION", "", "bên B có quyền đơn phương chấm dứt thực hiện hợp đồng", "TERMINATION"),
        R("CUSTOMER", "ANY_OBLIGATION", "", "yêu cầu bồi thường thiệt hại", "DAMAGES")]),
    ("K11", "SUPPLY_SERVICE", "q52", "4.7. Trường hợp Bên B đưa phương tiện đến nhận hàng chậm", None, SVC, [
        R("SUPPLIER", "PROVIDE_SERVICE", "LATE", "phải chịu phạt hợp đồng là", "PENALTY_FIXED", "", "carrier arrives late")]),
    ("K12", "SUPPLY_SERVICE", "q52", "14.4. Nếu Bên A vi phạm nghĩa vụ thanh toán tổng cước phí", None, SVC, [
        R("CUSTOMER", "PAY", "LATE", "phải chịu phạt theo mức lãi suất chậm trả", "INTEREST")]),
    ("K13", "SUPPLY_SERVICE", "q52", "14.2. Nếu Bên A đóng gói hàng mà không khai", None, SVC, [
        R("CUSTOMER", "NONE", "", "Bên A phải chịu phạt đến", "PENALTY_RATE", "", "misdeclaration: no key")]),
    ("K14", "SUPPLY_SERVICE", "q52", "Bồi thường thiệt hại cho Bên A trong trường hợp Bên B để mất mát", None, SVC, [
        R("SUPPLIER", "PROVIDE_SERVICE", "DEFECTIVE", "Bồi thường thiệt hại cho Bên A", "DAMAGES", "", "carrier loses goods")]),
    ("K15", "SUPPLY_SERVICE", "q53", "Trường hợp Bên A thanh toán chậm, Bên A phải chịu lãi phạt", None, SVC, [
        R("CUSTOMER", "PAY", "LATE", "Bên A phải chịu lãi phạt chậm trả", "INTEREST")]),
    ("K16", "SUPPLY_SERVICE", "q54", "Bên B có trách nhiệm bồi thường đối với những giá trị thiệt hại", None, SVC, [
        R("SUPPLIER", "PROVIDE_SERVICE", "DEFECTIVE", "Bên B có trách nhiệm bồi thường", "DAMAGES", "", "guard negligence"),
        R("SUPPLIER", "PAY", "LATE", "phải chịu hình thức phạt 0.05%", "PENALTY_RATE", "0.05", "late payment of compensation")]),
    ("K17", "SUPPLY_SERVICE", "q54", "Bên A thanh toán phí dịch vụ bảo vệ hàng tháng không đúng như cam kết", None, SVC, [
        R("CUSTOMER", "PAY", "LATE", "bên B có quyền chấm dứt hợp đồng trước thời hạn", "TERMINATION")]),
    ("K18", "SUPPLY_SERVICE", "q55", "Trong trường hợp Bên A thanh toán chậm cho Bên B", None, SVC, [
        R("CUSTOMER", "PAY", "LATE", "phải chịu mức phạt lãi suất chậm trả", "INTEREST"),
        R("CUSTOMER", "PAY", "LATE", "đồng thời bồi thường thiệt hại", "DAMAGES")]),
    ("K19", "LEASE", "q58", "Trường hợp Bên B chậm thanh toán, phải chịu lãi suất chậm trả", None, LSE, [
        R("LESSEE", "PAY", "LATE", "phải chịu lãi suất chậm trả", "INTEREST"),
        R("LESSEE", "PAY", "LATE", "mức phạt 8% trên tổng giá trị hợp đồng bị vi phạm", "PENALTY_RATE", "8")]),
    ("K20", "LEASE", "q57", "Trong trường hợp bên thuê tự ý thay đổi lộ trình", None, "", [
        R("LESSEE", "NONE", "", "bên thuê có thể phải chịu phạt vi phạm", "PENALTY_FIXED", "", "route change: no key")]),
    ("K21", "SUPPLY_SERVICE", "q49", "Bảo đảm và chịu trách nhiệm việc bồi thường giá trị", None, SVC, [
        R("SUPPLIER", "PROVIDE_SERVICE", "DEFECTIVE", "chịu trách nhiệm việc bồi thường giá trị", "DAMAGES", "", "bearer implicit (Bên B)")]),
    ("K22", "CONSTRUCTION_WORK", "q43", "Nếu Bên A chậm thanh toán cho Bên B, cụ thể là quá ba", None, OWN, [
        R("OWNER", "PAY", "LATE", "Bên B có quyền tạm ngưng thi công công trình", "SUSPENSION")]),
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
    out = pathlib.Path("evals/spikes/clause_key/heldout2.csv")
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    pathlib.Path("evals/spikes/clause_key/heldout2_sources.json").write_text(
        json.dumps(sources, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len({r["clause_id"] for r in rows}), "clauses,", len(rows), "frames")


if __name__ == "__main__":
    main()
