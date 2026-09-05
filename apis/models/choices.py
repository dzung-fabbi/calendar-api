"""Choice tuples shared across the model modules.

Names are kept exactly as they were when they lived at the top of models.py,
because migrations reference these values and the admin renders their labels.
"""

# The 60-term sexagenary cycle (can chi), upper-cased as stored for lunar days.
lunar_day = (
    ("GIÁP TÝ", "GIÁP TÝ"),
    ("ẤT SỬU", "ẤT SỬU"),
    ("BÍNH DẦN", "BÍNH DẦN"),
    ("ĐINH MÃO", "ĐINH MÃO"),
    ("MẬU THÌN", "MẬU THÌN"),
    ("KỶ TỴ", "KỶ TỴ"),
    ("CANH NGỌ", "CANH NGỌ"),
    ("TÂN MÙI", "TÂN MÙI"),
    ("NHÂM THÂN", "NHÂM THÂN"),
    ("QUÝ DẬU", "QUÝ DẬU"),
    ("GIÁP TUẤT", "GIÁP TUẤT"),
    ("ẤT HỢI", "ẤT HỢI"),
    ("BÍNH TÝ", "BÍNH TÝ"),
    ("ĐINH SỬU", "ĐINH SỬU"),
    ("MẬU DẦN", "MẬU DẦN"),
    ("KỶ MÃO", "KỶ MÃO"),
    ("CANH THÌN", "CANH THÌN"),
    ("TÂN TỴ", "TÂN TỴ"),
    ("NHÂM NGỌ", "NHÂM NGỌ"),
    ("QUÝ MÙI", "QUÝ MÙI"),
    ("GIÁP THÂN", "GIÁP THÂN"),
    ("ẤT DẬU", "ẤT DẬU"),
    ("BÍNH TUẤT", "BÍNH TUẤT"),
    ("ĐINH HỢI", "ĐINH HỢI"),
    ("MẬU TÝ", "MẬU TÝ"),
    ("KỶ SỬU", "KỶ SỬU"),
    ("CANH DẦN", "CANH DẦN"),
    ("TÂN MÃO", "TÂN MÃO"),
    ("NHÂM THÌN", "NHÂM THÌN"),
    ("QUÝ TỴ", "QUÝ TỴ"),
    ("GIÁP NGỌ", "GIÁP NGỌ"),
    ("ẤT MÙI", "ẤT MÙI"),
    ("BÍNH THÂN", "BÍNH THÂN"),
    ("ĐINH DẬU", "ĐINH DẬU"),
    ("MẬU TUẤT", "MẬU TUẤT"),
    ("KỶ HỢI", "KỶ HỢI"),
    ("CANH TÝ", "CANH TÝ"),
    ("TÂN SỬU", "TÂN SỬU"),
    ("NHÂM DẦN", "NHÂM DẦN"),
    ("QUÝ MÃO", "QUÝ MÃO"),
    ("GIÁP THÌN", "GIÁP THÌN"),
    ("ẤT TỴ", "ẤT TỴ"),
    ("BÍNH NGỌ", "BÍNH NGỌ"),
    ("ĐINH MÙI", "ĐINH MÙI"),
    ("MẬU THÂN", "MẬU THÂN"),
    ("KỶ DẬU", "KỶ DẬU"),
    ("CANH TUẤT", "CANH TUẤT"),
    ("TÂN HỢI", "TÂN HỢI"),
    ("NHÂM TÝ", "NHÂM TÝ"),
    ("QUÝ SỬU", "QUÝ SỬU"),
    ("GIÁP DẦN", "GIÁP DẦN"),
    ("ẤT MÃO", "ẤT MÃO"),
    ("BÍNH THÌN", "BÍNH THÌN"),
    ("ĐINH TỴ", "ĐINH TỴ"),
    ("MẬU NGỌ", "MẬU NGỌ"),
    ("KỶ MÙI", "KỶ MÙI"),
    ("CANH THÂN", "CANH THÂN"),
    ("TÂN DẬU", "TÂN DẬU"),
    ("NHÂM TUẤT", "NHÂM TUẤT"),
    ("QUÝ HỢI", "QUÝ HỢI"),
)

month = (
    (1, 1),
    (2, 2),
    (3, 3),
    (4, 4),
    (5, 5),
    (6, 6),
    (7, 7),
    (8, 8),
    (9, 9),
    (10, 10),
    (11, 11),
    (12, 12),
)

good_ugly_start = (
    (0, "Không xác định"),
    (1, "Sao tốt"),
    (2, "Sao xấu")
)

is_mountain = (
    (1, "Cung"),
    (2, "Sơn")
)

CALENDAR = (
    (1, "Âm lịch"),
    (2, "Tiết khí")
)

can_ngay = (
    ("Giáp", "Tý"),
    ("Ất", "Sửu"),
    ("Bính", "Dần"),
    ("Đinh", "Mão"),
    ("Mậu", "Thìn"),
    ("Kỷ", "Tỵ"),
    ("Canh", "Ngọ"),
    ("Tân", "Mùi"),
    ("Nhâm", "Thân"),
    ("Quý", "Dậu"),
)

tiet_khi = (
    ("Lập Xuân", "Lập Xuân"),
    ("Vũ Thủy", "Vũ Thủy"),
    ("Kinh Trập", "Kinh Trập"),
    ("Xuân Phân", "Xuân Phân"),
    ("Thanh Minh", "Thanh Minh"),
    ("Cốc Vũ", "Cốc Vũ"),
    ("Lập Hạ", "Lập Hạ"),
    ("Tiểu Mãn", "Tiểu Mãn"),
    ("Mang Chủng", "Mang Chủng"),
    ("Hạ Chí", "Hạ Chí"),
    ("Tiểu Thử", "Tiểu Thử"),
    ("Đại Thử", "Đại Thử"),
    ("Lập Thu", "Lập Thu"),
    ("Xử Thử", "Xử Thử"),
    ("Bạch Lộ", "Bạch Lộ"),
    ("Thu Phân", "Thu Phân"),
    ("Hàn Lộ", "Hàn Lộ"),
    ("Sương Giáng", "Sương Giáng"),
    ("Lập Đông", "Lập Đông"),
    ("Tiểu Tuyết", "Tiểu Tuyết"),
    ("Đại Tuyết", "Đại Tuyết"),
    ("Đông Chí", "Đông Chí"),
    ("Tiểu Hàn", "Tiểu Hàn"),
    ("Đại Hàn", "Đại Hàn"),
)

HOURS = (
    ("Tý", "Tý"),
    ("Sửu", "Sửu"),
    ("Dần", "Dần"),
    ("Mão", "Mão"),
    ("Thìn", "Thìn"),
    ("Tỵ", "Tỵ"),
    ("Ngọ", "Ngọ"),
    ("Mùi", "Mùi"),
    ("Thân", "Thân"),
    ("Dậu", "Dậu"),
    ("Tuất", "Tuất"),
    ("Hợi", "Hợi"),
)

AM_DUONG = (
    ("Âm quý", "Âm quý"),
    ("Dương quý", "Dương quý"),
)

cung_son = (
    (1, "Cung"),
    (2, "Son"),
)

direction = (
    ("Khảm", "Khảm"),
    ("Cấn", "Cấn"),
    ("Chấn", "Chấn"),
    ("Tốn", "Tốn"),
    ("Ly", "Ly"),
    ("Khôn", "Khôn"),
    ("Đoài", "Đoài"),
    ("Càn", "Càn"),
    ("Nhâm", "Nhâm"),
    ("Quý", "Quý"),
    ("Tý", "Tý"),
    ("Sửu", "Sửu"),
    ("Dần", "Dần"),
    ("Giáp", "Giáp"),
    ("Mão", "Mão"),
    ("Ất", "Ất"),
    ("Thìn", "Thìn"),
    ("Tốn", "Tốn"),
    ("Tỵ", "Tỵ"),
    ("Bính", "Bính"),
    ("Ngọ", "Ngọ"),
    ("Đinh", "Đinh"),
    ("Mùi", "Mùi"),
    ("Khôn", "Khôn"),
    ("Thân", "Thân"),
    ("Canh", "Canh"),
    ("Dậu", "Dậu"),
    ("Tân", "Tân"),
    ("Tuất", "Tuất"),
    ("Hợi", "Hợi"),
    ("Mậu", "Mậu"),
    ("Trung", "Trung"),
    ("Kỷ", "Kỷ"),
)

STATUS_TRANSACTION = (
    (0, 'Tạo mới'),
    (1, 'Hoàn thành')
)
