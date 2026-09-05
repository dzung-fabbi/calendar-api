---
phase: 5
title: "VN lunar va lich gio"
status: completed
priority: P1
effort: "2.5d"
dependencies: [3]
---

# Phase 5: `vn_lunar` + endpoint lịch giỗ

## Overview
Tự implement chuyển đổi âm ↔ dương lịch **Việt Nam (UTC+7)** và endpoint trả danh sách đám giỗ của cả dòng họ trong một khoảng thời gian.

**Đây là phase rủi ro cao nhất của cả plan.** Sai 1 ngày là hỏng tính năng chủ lực.

## Context Links
- [`plans/reports/researcher-260905-1107-vn-lunar-algorithm.md`](../reports/researcher-260905-1107-vn-lunar-algorithm.md) — đặc tả thuật toán, test vectors, xử lý ngày giỗ
- [`plans/reports/brainstorm-260905-1053-gia-pha-dong-ho.md`](../reports/brainstorm-260905-1053-gia-pha-dong-ho.md) mục 5.3

## Key Insights
- `lunarcalendar==0.0.9` đang dùng trong `apis/` là **lịch âm Trung Quốc, múi giờ UTC+8**. Lịch VN dùng UTC+7 → lệch ở một số năm.
- Ca lệch nổi tiếng cần dùng làm test: **Tết 1985** (VN 21/01 vs TQ 20/02 — lệch cả tháng do đặt tháng nhuận khác nhau, **ĐÃ KIỂM CHỨNG ĐÚNG**) và **Tết 2007** (VN 17/02 vs TQ 18/02 — lệch 1 ngày do múi giờ). **Lưu ý:** báo cáo researcher ban đầu chạy ở tz=8 (lịch TQ) nên ghi sai 1985 là 20/02 — đã được đính chính trong báo cáo.
- **Không đụng vào `apis/`.** Almanac giữ nguyên `lunarcalendar` để không phải ghi lại golden snapshots. Đây là mâu thuẫn có chủ đích, phải ghi vào `docs/system-architecture.md` ở phase 10.

## Architecture

### `giapha/services/vn_lunar.py`
Thuật toán Hồ Ngọc Đức, thuần Python, **không thêm dependency**, `TIMEZONE = 7`.

Các hàm bắt buộc:
```
jd_from_date(dd, mm, yy) -> int              # Julian Day Number
jd_to_date(jd) -> (dd, mm, yy)
new_moon_day(k, tz) -> int                   # JDN của Sóc thứ k tính từ 1900-01-31
sun_longitude(jdn, tz) -> int                # 0..11, xác định Trung khí
lunar_month_11(yy, tz) -> int                # JDN mùng 1 tháng 11 âm của năm yy
leap_month_offset(a11, tz) -> int            # vị trí tháng nhuận
solar_to_lunar(dd, mm, yy, tz) -> (d, m, y, is_leap)
lunar_to_solar(d, m, y, is_leap, tz) -> (dd, mm, yy)
```

⚠️ **Việc đầu tiên phải làm**: đối chiếu ánh xạ `k` (số thứ tự Sóc) → số tháng âm lịch với bản tham chiếu gốc của Hồ Ngọc Đức. Báo cáo researcher **để ngỏ điểm này** và đó chính là lõi thuật toán. Nguồn đối chiếu: bản JavaScript gốc `amlich-hnd.js` của Hồ Ngọc Đức, hoặc port `vanng822/amlich`. **Không tự suy diễn.**

Khoảng năm tin cậy: **1800–2199** (chính xác nhất 1900–2100). Ngoài khoảng → raise `ValueError`, view trả 400.

### `giapha/services/gio.py` — quy tắc ngày giỗ

Hai quy tắc tập quán, ảnh hưởng trực tiếp kết quả:

| Tình huống | Xử lý |
|---|---|
| Mất ngày **30** nhưng năm nay tháng đó chỉ có **29 ngày** | Giỗ vào ngày **29** |
| Mất trong **tháng nhuận** | Giỗ vào **tháng thường tương ứng**, không đợi năm có nhuận |
| Mất trong tháng thường, năm nay tháng đó có nhuận | Giỗ vào **tháng thường**, bỏ qua tháng nhuận |

Hàm chính:
```python
def gio_solar_date(death_lunar_day, death_lunar_month, lunar_year) -> date
```
Thuần Python, không ORM → test `SimpleTestCase`.

Lưu ý về **năm**: một năm dương lịch có thể chứa **hai** lần giỗ của cùng một người (ví dụ giỗ tháng Chạp âm rơi vào tháng 1 dương của năm này và cũng có thể rơi vào tháng 12 dương). Endpoint nhận khoảng dương lịch `from`/`to`, và phải quét đủ các năm âm giao nhau với khoảng đó — **không** giả định 1 người = 1 giỗ/năm.

### Response `lich-gio`
```json
{"items": [
  {"person_id": 12, "ho_ten": "Nguyễn Đình A", "thuy_hieu": "...",
   "generation": 3,
   "lunar": {"day": 12, "month": 8},
   "solar_date": "2026-09-23",
   "can_chi_ngay": "Giáp Tý",
   "days_until": 18,
   "adjusted": false}
]}
```
`adjusted: true` khi đã lùi từ ngày 30 về 29 — client nên hiển thị ghi chú.

`can_chi_ngay` lấy từ `apis/services/can_chi.py::can_chi_for_date`. **Đây là ngoại lệ import duy nhất được phép** từ `apis/` sang `giapha/`: hàm thuần, không ORM, không state. Nếu thấy gợn, sao chép hàm 3 dòng đó sang `giapha/services/` để giữ hai app hoàn toàn độc lập — **quyết định khi implement, ghi rõ lý do vào comment.**

## Related Code Files

**Create**
- `giapha/services/vn_lunar.py`
- `giapha/services/gio.py`
- `giapha/selectors/gio.py` — nạp người đã mất của clan (1 query, dùng index `(clan, death_lunar_month, death_lunar_day)` từ phase 1)
- `giapha/serializers/gio.py`
- `giapha/views/gio.py`
- `giapha/tests/test_vn_lunar.py` (SimpleTestCase — test vectors)
- `giapha/tests/test_gio_service.py` (SimpleTestCase)
- `giapha/tests/test_gio_api.py`

**Modify**
- `giapha/urls.py`

## Endpoints
```
GET /api/gia-pha/clans/{clan_id}/lich-gio?from=YYYY-MM-DD&to=YYYY-MM-DD   IsClanMember
GET /api/gia-pha/clans/{clan_id}/lich-gio?year=YYYY                        (tiện dụng: cả năm dương)
```
Khoảng `from..to` tối đa **2 năm**; dài hơn trả 400. Mặc định khi không truyền: 12 tháng tới.

## Implementation Steps
1. **Trước khi viết code**: lấy bản tham chiếu gốc của Hồ Ngọc Đức, xác định dứt điểm ánh xạ `k → lunar_month` và cách đánh dấu tháng nhuận. Ghi nguồn vào docstring của `vn_lunar.py`.
2. Viết `vn_lunar.py` với `TIMEZONE = 7` là hằng số module, không phải tham số mặc định rải rác.
3. **Viết test vectors TRƯỚC khi tin vào code.** Tối thiểu 15 cặp, bắt buộc gồm:
   - Tết 1985: VN 21/01/1985 = 01/01 ÂL (khác TQ)
   - Tết 2007: VN 17/02/2007 = 01/01 ÂL (khác TQ)
   - ≥ 3 năm VN trùng TQ (2021, 2023, 2025) để chứng minh không phá ca thường
   - ≥ 2 năm có tháng nhuận, gồm ngày trong chính tháng nhuận
   - biên: 1800 và 2199
   - **Mỗi vector phải có nguồn ghi kèm trong comment.** Không chấp nhận số liệu không truy nguyên được.
4. Test đối sánh chéo: với các năm mà VN trùng TQ, `vn_lunar` phải cho cùng kết quả với `lunarcalendar` đang có. Chỗ nào lệch phải giải thích được bằng múi giờ, không phải bằng bug.
5. Viết `gio.py` với 3 quy tắc tập quán ở bảng trên, mỗi quy tắc ≥ 2 test.
6. Viết selector: lọc `death_lunar_month__isnull=False`, một query, `values()` chỉ các trường cần.
7. Viết view: chuyển khoảng dương `from..to` sang tập năm âm cần quét, tính giỗ cho từng người, lọc về đúng khoảng, sắp theo `solar_date`.
8. Ghi query budget cho endpoint vào snapshot.

## Success Criteria
- [x] Toàn bộ 15+ test vector xanh, **mỗi vector có nguồn truy nguyên được**
- [x] Tết 1985 và 2007 khớp lịch VN, khác lịch TQ — chứng minh UTC+7 hoạt động
- [x] Các năm VN trùng TQ cho kết quả giống `lunarcalendar`
- [x] Ngày 30 tháng thiếu lùi về 29, cờ `adjusted=true`
- [x] Mất tháng nhuận → giỗ tháng thường
- [x] Ngoài khoảng 1800–2199 → 400, không trả kết quả sai âm thầm
- [x] `lich-gio` cho clan 1.000 người dùng ≤ 2 query
- [x] `vn_lunar.py` và `gio.py` test được bằng `SimpleTestCase`
- [x] `apis/` không bị sửa; suite hiện có vẫn xanh

## Kết quả thực tế

**Files tạo mới:**
- `giapha/services/vn_lunar.py` — thuật toán Hồ Ngọc Đức, UTC+7
- `giapha/services/gio.py` — quy tắc tập quán ngày giỗ
- `giapha/services/can_chi.py` — Thiên can Địa chi (sao chép từ `apis/services/can_chi.py`)
- `giapha/selectors/gio.py` — selector nạp người mất của clan
- `giapha/serializers/gio.py` — serializer response lich-gio
- `giapha/views/gio.py` — view endpoint
- `giapha/tests/test_vn_lunar.py` — test vectors lịch âm (SimpleTestCase)
- `giapha/tests/test_gio_service.py` — test quy tắc ngày giỗ (SimpleTestCase)
- `giapha/tests/test_gio_api.py` — test endpoint

**Files sửa:**
- `giapha/urls.py` — thêm route lich-gio
- `giapha/selectors/__init__.py`, `giapha/serializers/__init__.py`, `giapha/views/__init__.py` — export wiring

**Endpoint thêm vào:**
- `GET /api/gia-pha/clans/{clan_id}/lich-gio?from=YYYY-MM-DD&to=YYYY-MM-DD` — danh sách giỗ trong khoảng
- `GET /api/gia-pha/clans/{clan_id}/lich-gio?year=YYYY` — giỗ trong năm dương

**Kiểm chứng:**
- 356 test xanh (50 `apis` + 306 `giapha`), 0 failure, 4 skipped
- Differential 146.097 ngày (1800–2199) vs amlich.js gốc: 0 sai lệch
- Năm VN = TQ ở tz=8: 0 sai lệch với `lunarcalendar`
- Năm VN ≠ TQ: 1968, 1969, 1985, 2007 — tất cả khớp UTC+7, có test cho từng năm
- Endpoint query budget: ≤ 2 queries bất kể kích cỡ clan

## Risk Assessment
- **Rủi ro số 1 của cả plan.** Ngày giỗ sai là lỗi mất mặt với người dùng ở mức không sửa được bằng lời xin lỗi. Không merge phase này nếu test vectors chưa đủ nguồn.
- **Ánh xạ `k → tháng` chưa chốt** (researcher để ngỏ). Nếu không tìm được bản tham chiếu đáng tin, **dừng và báo lại** — không đoán.
- **Test vectors lấy từ web có thể sai.** Ưu tiên nguồn chéo ≥ 2, và ưu tiên lịch in truyền thống VN hơn website tính tự động.
- **Hai app dùng hai lịch âm khác nhau** là mâu thuẫn thật. Có chủ đích, nhưng phải ghi vào docs, nếu không người sau sẽ "sửa" nó thành một.
- **Cám dỗ tính giỗ theo ngày dương.** Tuyệt đối không. Ngày dương chỉ để tham chiếu.

## Next Steps
Phase 6 (FCM push) phụ thuộc trực tiếp vào `gio.py` của phase này.
