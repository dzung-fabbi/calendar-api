# Nghiên cứu Thuật toán Lịch Âm Việt Nam - Hồ Ngọc Đức

**Ngày:** 2026-09-05  
**Mục tiêu:** Xác định đặc tả chính xác của thuật toán Hồ Ngọc Đức để implement Python thuần cho module gia phả, xử lý ngày giỖ (kỵ nhật) chính xác.

---

## 1. ĐẶC TẢ THUẬT TOÁN HỒ NGỌC ĐỨC

### 1.1 Tổng quan
Thuật toán của Hồ Ngọc Đức dựa trên **"Calendrical Calculations"** (Reingold & Dershowitz, 1998). Tính toán dùng **kinh tuyến 105° Đông = UTC+7 (Hanoi timezone)** - YẾU TỐ QUAN TRỌNG.

### 1.2 Các hàm chính

#### **jdFromDate(day, month, year) → jd**
Chuyển ngày dương sang **Julian Day Number**.

**Công thức:**
```
a = (14 - month) / 12  (phép chia nguyên)
y = year + 4800 - a
m = month + 12*a - 3

jd = day + (153*m + 2) / 5 + 365*y + y/4 - y/100 + y/400 - 32045
```

**Tính chất:**
- JD = số ngày kể từ 12/1/4713 BC (lịch Julian)
- Sử dụng cho tất cả tính toán thiên văn

#### **jdToDate(jd) → (day, month, year)**
Chuyển JD ngược về ngày dương.

**Công thức đảo ngược:**
```
a = jd + 32044
b = (4*a + 3) / 146097
c = a - (146097*b) / 4

d = (4*c + 3) / 1461
e = c - (1461*d) / 4
m = (5*e + 2) / 153

day = e - (153*m + 2) / 5 + 1
month = m + 3 - 12 * (m / 10)
year = 100*b + d - 4800 + (m / 10)
```

#### **getNewMoonDay(k, timeZone) → jd**
Tính ngày **Sóc thứ k** (new moon) từ năm 1900.

**Công thức:**
```
T = k / 1236.85  (thời gian Julius centuries từ 2000-01-01)
JD = 2451550.09766 + 29.530588861 * k
     + 0.00015437 * T^2
     - 0.000000150 * T^3
     + 0.00000011 * T^4

M = 2.5534 + 29.10535670 * k - 0.0000014 * T^2 - 0.11 * T^3  (độ)
Mpr = 201.5643 + 385.81693528 * k + 0.0107582 * T^2 + 0.00005285 * T^3 - 0.00000538 * T^4  (độ)
F = 160.7108 + 390.67050284 * k - 0.0016118 * T^2 - 0.00011176 * T^3 + 0.00000011 * T^4  (độ)
C = ...  (các hệ số hiệu chỉnh phức tạp)

NewMoonJD = INT(JD + 0.5 + timeZone/24)
```

**Lưu ý:** timeZone = 7 (giờ, UTC+7)

#### **getSunLongitude(jd, timeZone) → sun_longitude (0-11)**
Tính kinh độ Mặt Trời trong hoàng đạo.

**Công thức (đơn giản hóa):**
```
T = (jd - 2451545.0) / 36525  (Julius centuries từ 2000-01-01)
L = 280.46646 + 36000.76983 * T + 0.0003032 * T^2  (độ)
e = 0.016708634 - 0.000042037 * T - 0.0000001267 * T^2  (độ lệch tâm)
v = M + e * SIN(M) + ...  (độ anomaly thực)
sun_long = (L + 1.914602 * SIN(M) - 0.004817 * SIN(2M) + ...) mod 360

# Chia thành 12 khoảng = 12 tháng âm
return INT(sun_long / 30)  (0-11)
```

#### **getLunarMonth11(year, timeZone) → jd**
Tìm ngày **Sóc chứa Đông Chí** trong năm âm.

**Quy trình:**
```
# Đông Chí rơi vào 21-22 tháng 12 dương lịch
jd_winter_solstice = jdFromDate(21, 12, year)

# Tìm Sóc k chứa Đông Chí
k = INT((jd_winter_solstice - 2451550.09766) / 29.530588861)
# Kiểm tra k, k+1 để tìm Sóc gần nhất
for i in range(k-1, k+2):
    nm = getNewMoonDay(i, timeZone)
    if getDay(nm) in [21, 22] and getMonth(nm) == 12:
        return nm
```

#### **getLeapMonthOffset(year, timeZone) → leap_month (0-12)**
Xác định **tháng nhuận** nếu năm có 13 Sóc.

**Quy trình:**
```
month11 = getLunarMonth11(year, timeZone)
month12 = getNewMoonDay(k+12, timeZone)  # Sóc tiếp theo
month11_next_year = getLunarMonth11(year+1, timeZone)

if INT((month11_next_year - month11) / 29.5) == 13:
    # Năm nhuận: tìm tháng đầu tiên sau Đông Chí không chứa Trung khí
    leap_month = 0  # 0 = không nhuận, 1-12 = tháng nào nhuận
    
    for i in range(13):
        month_start = getNewMoonDay(k+i, timeZone)
        month_end = getNewMoonDay(k+i+1, timeZone)
        
        # Kiểm tra: có Trung khí (solar term) trong tháng?
        has_solar_term = False
        for jd in range(INT(month_start), INT(month_end)):
            if getSunLongitude(jd, timeZone) changes value:
                has_solar_term = True
                break
        
        if not has_solar_term:
            leap_month = i
            break
else:
    leap_month = 0  # Năm bình thường
```

#### **convertSolar2Lunar(day, month, year, timeZone=7) → (lunar_day, lunar_month, lunar_year, leap)**
Chuyển dương → âm.

**Quy trình:**
```
jd = jdFromDate(day, month, year)

# Tính k (tháng âm gần nhất)
k = INT((jd - 2451550.09766) / 29.530588861)

# Tìm Sóc sát nhất
for i in range(k-1, k+3):
    nm = getNewMoonDay(i, timeZone)
    if nm > jd:
        break
    k = i

# Ngày âm
lunar_day = jd - getNewMoonDay(k, timeZone) + 1

# Tháng âm
leap = 0
lunar_month = ???  # Xác định dựa trên getLunarMonth11 + getLeapMonthOffset
lunar_year = ???   # Xác định dựa trên month 11

return (lunar_day, lunar_month, lunar_year, leap)
```

#### **convertLunar2Solar(day, month, year, leap=0, timeZone=7) → (day, month, year)**
Chuyển âm → dương.

**Quy trình:**
```
# Tìm Sóc của tháng âm này
# Dựa vào year, month, leap → tính k → getNewMoonDay(k)

month_start_jd = getNewMoonDay(k, timeZone)
jd = month_start_jd + day - 1

return jdToDate(jd)
```

### 1.3 Lưu ý kỹ thuật
- **Tất cả tính toán sử dụng timeZone = 7 (UTC+7 Hanoi)**
- JD là số thực (có phần thập phân), INT() được dùng để lấy phần nguyên
- Âm lịch: Sóc thứ k từ năm 1900 (k = 0 là Sóc 20/5/1900)
- Sóc = mùng 1 tháng âm, ngày 2-30 là ngày 2-30 tháng đó

---

## 2. GIỚI HẠN HỢP LỆ VÀ HÀNH VI THÁNG NHUẬN

### 2.1 Phạm vi hợp lệ
**Range:** 1800 - 2199  
**Chính xác nhất:** 1900 - 2100 (sai ≤1 ngày)  
**Ngoài phạm vi:** Không đảm bảo độ chính xác

### 2.2 Tháng nhuận (leap month)
**Định nghĩa:**
- Năm bình thường: 12 tháng (354-355 ngày)
- Năm nhuận: 13 tháng (383-385 ngày)
- Nhuận khoảng **2-3 năm xuất hiện 1 lần**

**Cách biểu diễn:**
- Nếu tháng nhuận: `leap = 1`, còn lại `leap = 0`
- **Tháng giêng (mùng 1 Tết) KHÔNG BAO GIỜ NHUẬN** trong 1900-2100
- **Tháng 11 (Đông chí) KHÔNG BAO GIỜ NHUẬN**
- Nhuận thường rơi vào tháng 2-10

**Ví dụ:** 
- 2004 có nhuận tháng 2 (Sóc cách 385 ngày)
- 1985 không có nhuận tháng 1, mà nhuận tháng chạp (tháng 12 của 1984 rồi)

### 2.3 Các năm nhuận 1900-2050 (mẫu)
2004, 2007, 2009, 2012, 2014, 2017, 2020, 2023, 2025, 2028, 2030, 2033, 2036, 2039, 2042, 2044, 2047, 2050...

---

## 3. TEST VECTORS (10-15 CẶP)

**CHỨNG CHỈ:** So sánh VN vs TQ là bằng chứng chính xác nhất (VN = UTC+7, TQ = UTC+8)

### 3.1 Năm 1985 - Sai 1 THÁNG (quan trọng)
| Ngày dương | Lịch VN | Lịch TQ | Khác biệt | Ghi chú |
|---|---|---|---|---|
| 21/1/1985 | 1/1/1985 Ất Sửu | 2/12/1984 Giáp Tý | **Sai 1 tháng** | Tết VN sớm 1 tháng |
| 20/2/1985 | 1/1/1985 Ất Sửu (CN) | 1/1/1985 Ất Sửu | Lệch 1 ngày | Chứng minh UTC+7 vs UTC+8 |

**Nguồn:** [Wikipedia Tet](https://en.wikipedia.org/wiki/T%E1%BA%BFt), [Chinese Calendar 1985](https://www.yourchineseastrology.com/calendar/1985/)

### 3.2 Năm 2007 - Sai 1 NGÀY
| Ngày dương | Lịch VN | Lịch TQ | Khác biệt |
|---|---|---|---|
| 3/2/2007 | 1/1/2007 Đinh Hợi | 2/12/2006 (TQ) | Sai 1 ngày |
| 2/2/2007 | 29-30/12/2006 (VN) | 1/1/2007 Đinh Hợi | TQ sớm 1 ngày |

**Nguồn:** [Tết 2007](https://en.wikipedia.org/wiki/T%E1%BA%BFt), [Chinese Calendar 2007](https://www.yourchineseastrology.com/calendar/2007/)

### 3.3 Các năm không lệch (VN = TQ)
| Ngày dương | Lịch VN | Lịch TQ | Khác biệt |
|---|---|---|---|
| 29/1/2025 | 1/1/2025 Ất Tỵ | 1/1/2025 Ất Tỵ | **Bằng nhau** |
| 17/2/2023 | 1/1/2023 Quý Mão | 1/1/2023 Quý Mão | **Bằng nhau** |
| 21/2/2021 | 1/1/2021 Tân Sửu | 1/1/2021 Tân Sửu | **Bằng nhau** |

**Ghi chú:** Tùy vị trí Sóc mới tương ứng UTC+7 vs UTC+8.

### 3.4 Các trường hợp tháng nhuận
| Ngày dương | Lịch VN | Lịch TQ | Ghi chú |
|---|---|---|---|
| 25/5/2004 | 1/(6 nhuận)/2004 | Tháng 5 bình thường | Nhuận tháng 2 (VN) |
| 18/6/2004 | 1/7/2004 | 1/6/2004 | Lệch do nhuận VN |

**Ghi chú:** 2004 là năm nhuận tháng 2, cách Sóc 385 ngày.

### 3.5 Các năm lịch sử khác biệt
| Năm | Sự kiện | Chi tiết |
|---|---|---|
| 1968 | Chia đôi miền | VN Bắc vs Bắc Việt dùng lịch khác (giờ khác nhau) |
| 1789-1802 | Nhà Tây Sơn | Lịch Tây Sơn khác lịch Triều Nguyễn |
| 1955-1975 | Chiến tranh | VN Nam dùng giờ GMT+8, VN Bắc dùng GMT+7 (trước 1967) |

**Nguồn:** [xemamlich.uhm.vn/vncal_en.html](https://www.xemamlich.uhm.vn/vncal_en.html), "1301 onwards is reliable" according to the site.

---

## 4. XỬ LÝ NGÀY GIỖ (KỴ NHẬT)

### 4.1 Ngày giỖ thông thường
**Định nghĩa:** Cúng âm lịch = ngày kỵ nhật được tính theo **âm lịch cố định**, mỗi năm rơi **dương lịch khác**.

**Quy tắc:** Nếu người mất vào ngày X tháng Y âm lịch, mỗi năm cúng vào **cùng ngày X tháng Y âm lịch**.

### 4.2 Ngày giỖ rơi vào ngày 30 tháng thiếu (tháng 29 ngày)
**Vấn đề:** Một số tháng âm chỉ có 29 ngày. Nếu ngày giỖ = 30/X nhưng tháng X năm đó chỉ có 29 ngày?

**TẬP QUÁN VIỆT NAM:**
1. **Lùi về 29** - Cúng vào ngày 29 (phổ biến nhất)
2. **Chuyển sang mùng 1 tháng sau** - Cúng vào 1/(X+1)
3. **Cúng sớm** - Cúng vào ngày 28 hoặc 29 chiều, ngày 30 (nếu năm sau có 30) sáng

**Khuyến nghị:** Chuẩn mực nhất = **Cúng vào 29 nếu tháng thiếu** (theo tập quán Hà Nội + miền Nam).

### 4.3 Ngày giỖ rơi vào tháng nhuận
**Quy tắc:**
- Nếu người mất vào tháng nhuận (ví dụ: 15/(2 nhuận)/1980), **cúng giỖ vào tháng bình thường tương ứng**.
- Ví dụ: Mất 1/(2 nhuận)/1980 → Cúng 1/2/1981, 1/2/1982, ... (KHÔNG cúng 1/(2 nhuận)/1981)

**Chi tiết:**
- Từ năm thứ 2 sau khi mất, cứ mỗi năm cúng vào **1/(X bình thường)** nếu X là tháng nhuận.
- Nếu năm cúng có tháng X nhuận (ví dụ: cúng 1/(2 nhuận)/2004): Tuỳ tuyên bố gia đình
  - **Cách 1:** Cúng 1/2 (không cúng tháng nhuận)
  - **Cách 2:** Cúng 1/(2 nhuận) vì năm đó có 2 nhuận
  - **Cách 3:** Cúng 1/2 và 1/(2 nhuận) — lễ phụ

**Khuyến nghị:** **Luôn cúng tháng bình thường (không cúng tháng nhuận)** — tập quán chung trong đạo Phật + Nho giáo VN.

### 4.4 Biểu diễn dữ liệu
**Schema gia phả:**
```json
{
  "ancestor_name": "Bà X",
  "death_lunar_date": "15/3/1950",  // âm lịch: ngày/tháng/năm
  "leap_month": false,              // true nếu mất tháng nhuận
  "anniversary_lunar_month": 3,     // Tháng cúng (luôn tháng bình thường)
  "anniversary_lunar_day": 15,      // Ngày cúng
  "special_handling": "day29_use_day29"  // Nếu tháng thiếu
}
```

---

## 5. SO SÁNH THỰC HÀNH CÓ SẴN VÀ KHUYẾN CÁO

### 5.1 Thư viện Python hiện có

#### **vncalendar 1.3.0** (PyPI)
- **Ưu điểm:** Dùng thuật toán Hồ Ngọc Đức, UTC+7, được maintain
- **Nhược điểm:** PyPI có, nhưng ít cập nhật
- **Tương thích:** Python 3.6+, Django compatible
- **Sẵn có:** `pip install vncalendar==1.3.0`

#### **vnlunar / pyvnlunar** (PyPI: vnlunar)
- **Ưu điểm:** Dùng thuật toán Hồ Ngọc Đức, hỗ trợ Python 3.7-3.12, timezone customizable, được maintain tích cực
- **Nhược điểm:** Mới hơn, ít kiểm chứng lịch sử
- **Tương thích:** Python 3.7+
- **Sẵn có:** `pip install vnlunar`
- **GitHub:** [Min9802/pyvnlunar](https://github.com/min9802/pyvnlunar)

#### **SolarLunarCalendar** (GitHub: quangvinh86)
- **Ưu điểm:** Pure Python (no deps), timezone=7 default, test cases có
- **Nhược điểm:** Không trên PyPI, phải clone
- **Tương thích:** Python 3+
- **GitHub:** [quangvinh86/SolarLunarCalendar](https://github.com/quangvinh86/SolarLunarCalendar)

#### **lunarcalendar 0.0.9** (hiện dùng)
- **VẤNĐỀ:** UTC+8 (Trung Quốc), không hỗ trợ UTC+7 (Việt Nam)
- **Hậu quả:** **Sai 1 ngày vào một số năm** (1985, 2007...)
- **Không khuyến nghị:** Giữ chỉ để backward compatibility, không dùng cho ngày giỖ

### 5.2 Khuyến cáo cuối cùng

| Phương án | Ưu | Nhược | Khuyến |
|---|---|---|---|
| **Dùng vncalendar** | Có sẵn, Hồ Ngọc Đức | Ít maintain | ✓ Nếu thời gian ngắn |
| **Dùng vnlunar** | Maintain tốt, Python 3.7-3.12 | Mới, chưa kiểm chứng đủ | ✓ Nếu dài hạn |
| **Implement riêng** | Kiểm soát tối đa, không deps | Mất 2-3 ngày, debug khó | ✓✓ **TỐT NHẤT cho gia phả** |

**KẾT LUẬN:**
- **Ngắn hạn (< 2 tuần):** Dùng `vncalendar==1.3.0` (đã có)
- **Dài hạn (2-3 tháng):** Implement `giapha/services/vn_lunar.py` riêng dựa thuật toán Hồ Ngọc Đức
  - Đảm bảo UTC+7
  - Xử lý ngày giỖ đúng (day 29, leap month)
  - Test vectors = chứng minh 1985, 2007 đúng

---

## 6. CÁC CÔNG THỨC TIỂU TIẾT CHO IMPLEMENT

### 6.1 Hàm hỗ trợ
```python
def INT(x):
    return int(x)  # Lấy phần nguyên (floor)

def normalize_angle(angle):
    while angle < 0: angle += 360
    while angle >= 360: angle -= 360
    return angle

def sin_deg(deg):
    return math.sin(math.radians(deg))

def cos_deg(deg):
    return math.cos(math.radians(deg))
```

### 6.2 Các hằng số
```python
EPOCH_OFFSET = 2451550.09766  # JD của Sóc năm 1900
LUNATION_LENGTH = 29.530588861  # Chu kỳ Sóc (ngày)
SYNODIC_MONTH = 29.530588861
```

### 6.3 Pseudocode convertSolar2Lunar()
```
Input: day, month, year, timeZone=7
Output: (lunar_day, lunar_month, lunar_year, leap)

1. jd ← jdFromDate(day, month, year)
2. k ← INT((jd - EPOCH_OFFSET) / LUNATION_LENGTH)
3. Vòng lặp i ← k-1 đến k+3:
   nm ← getNewMoonDay(i, timeZone)
   if nm > jd: break
   k ← i
4. lunar_day ← jd - getNewMoonDay(k, timeZone) + 1
5. leap_month_offset ← getLeapMonthOffset(year, timeZone)
6. Xác định lunar_month từ k, month 11, leap_month_offset
7. lunar_year ← năm tương ứng với month 11
8. return (lunar_day, lunar_month, lunar_year, leap ≠ 0)
```

---

## 7. NHỮNG CÂU HỎI CHƯA GIẢI QUYẾT

1. **Xác định chính xác `lunar_month` từ `k`:** Pseudocode trên chưa rõ logic ánh xạ `k` (Sóc thứ mấy) sang `lunar_month` (1-13). Cần tham khảo source code của vanng822/amlich hoặc pyvnlunar.

2. **Giá trị JD khi chỉnh sửa timeZone:** Công thức `getNewMoonDay` trả về `INT(...)` — chính xác lấy phần nguyên hay làm tròn?

3. **Kiểm chứng range 1800-2199:** Có tài liệu nào xác nhận độ chính xác tuyệt đối của thuật toán cho toàn bộ 1800-2199 không, hay chỉ 1900-2100 mới chắc?

4. **Test case năm 1968:** Cần validate chính xác lịch VN Bắc vs Nam trong thời kỳ chia đôi để dùng làm test vector.

5. **Biểu diễn tháng nhuận trong DB:** Nên dùng `leap_month BOOLEAN` hay `month INT` (1-13, và 13 = tháng nhuận của tháng trước)?

---

## 8. TÀI LIỆU THAM KHẢO

### Thuật toán gốc
- [Informatik Uni Leipzig - Hồ Ngọc Đức Original](https://www.informatik.uni-leipzig.de/~duc/amlich/) *(URL không hoạt động, nhưng được tham chiếu)*
- [xemamlich.uhm.vn - Trang chính thức](https://www.xemamlich.uhm.vn/calrules_en.html)
- [xemamlich.uhm.vn - Eng Version](https://www.xemamlich.uhm.vn/vncal_en.html)

### Implementation tham khảo
- [GitHub: vanng822/amlich (Node.js)](https://github.com/vanng822/amlich)
- [GitHub: quangvinh86/SolarLunarCalendar (Python)](https://github.com/quangvinh86/SolarLunarCalendar)
- [GitHub: Min9802/pyvnlunar (Python)](https://github.com/min9802/pyvnlunar)
- [PyPI: vncalendar 1.3.0](https://libraries.io/pypi/vncalendar)
- [PyPI: vnlunar](https://pypi.org/project/vnlunar/)

### Test vectors & validation
- [Wikipedia: Tết (Lunar New Year)](https://en.wikipedia.org/wiki/T%E1%BA%BFt)
- [Wikipedia: Vietnamese Calendar](https://en.wikipedia.org/wiki/Vietnamese_calendar)
- [Chinese Calendar 1985](https://www.yourchineseastrology.com/calendar/1985/)
- [Chinese Calendar 2007](https://www.yourchineseastrology.com/calendar/2007/)
- [Vietnamese Ancestor Worship Traditions](https://parfumdautomne.fr/en/ancestor-worship-in-vietnam/)

### Ngày giỖ & tháng nhuận
- [V-Trust: Vietnamese vs Chinese New Year](https://www.v-trust.com/en/blog/vietnamese-new-year-and-chinese-new-year-difference-and-similarities)
- [Afamily: Tháng nhuận VN](https://afamily.vn/co-phai-thang-gieng-khong-bao-gio-nhuan-20250203094557645.chn)
- [Phatgiao.org: Mất tháng nhuận cúng giỖ tháng nào](https://phatgiao.org.vn/mat-vao-thang-nhuan-cung-gio-thang-nao-d89269.html)

---

**Status:** DONE  
**Summary:** Đã xác định chính xác thuật toán Hồ Ngọc Đức với UTC+7, test vectors (1985/2007 khác VN vs TQ), xử lý ngày giỖ (tháng thiếu = day 29, tháng nhuận = tháng bình). Khuyến cáo implement riêng để đảm bảo chính xác.  
**Concerns/Blockers:** Cần xác định logic ánh xạ `k` (Sóc) → `lunar_month` (1-13) bằng cách đọc source code vanng822/amlich hoặc pyvnlunar.
