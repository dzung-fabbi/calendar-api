/* Vietnamese lunar calendar (Hồ Ngọc Đức algorithm, UTC+7) + giỗ helpers.
   Same algorithm family as giapha/services/vn_lunar.py, so dates match the backend. */
(function (g) {
  const TZ = 7, PI = Math.PI, INT = Math.floor;

  function jdFromDate(dd, mm, yy) {
    const a = INT((14 - mm) / 12), y = yy + 4800 - a, m = mm + 12 * a - 3;
    let jd = dd + INT((153 * m + 2) / 5) + 365 * y + INT(y / 4) - INT(y / 100) + INT(y / 400) - 32045;
    if (jd < 2299161) jd = dd + INT((153 * m + 2) / 5) + 365 * y + INT(y / 4) - 32083;
    return jd;
  }
  function jdToDate(jd) {
    let b, c;
    if (jd > 2299160) { const a = jd + 32044; b = INT((4 * a + 3) / 146097); c = a - INT((b * 146097) / 4); }
    else { b = 0; c = jd + 32082; }
    const d = INT((4 * c + 3) / 1461), e = c - INT((1461 * d) / 4), m = INT((5 * e + 2) / 153);
    return [e - INT((153 * m + 2) / 5) + 1, m + 3 - 12 * INT(m / 10), b * 100 + d - 4800 + INT(m / 10)];
  }
  function newMoon(k) {
    const T = k / 1236.85, T2 = T * T, T3 = T2 * T, dr = PI / 180;
    let jd1 = 2415020.75933 + 29.53058868 * k + 0.0001178 * T2 - 0.000000155 * T3;
    jd1 += 0.00033 * Math.sin((166.56 + 132.87 * T - 0.009173 * T2) * dr);
    const M = 359.2242 + 29.10535608 * k - 0.0000333 * T2 - 0.00000347 * T3;
    const Mpr = 306.0253 + 385.81691806 * k + 0.0107306 * T2 + 0.00001236 * T3;
    const F = 21.2964 + 390.67050646 * k - 0.0016528 * T2 - 0.00000239 * T3;
    let C1 = (0.1734 - 0.000393 * T) * Math.sin(M * dr) + 0.0021 * Math.sin(2 * dr * M);
    C1 = C1 - 0.4068 * Math.sin(Mpr * dr) + 0.0161 * Math.sin(dr * 2 * Mpr) - 0.0004 * Math.sin(dr * 3 * Mpr);
    C1 = C1 + 0.0104 * Math.sin(dr * 2 * F) - 0.0051 * Math.sin(dr * (M + Mpr));
    C1 = C1 - 0.0074 * Math.sin(dr * (M - Mpr)) + 0.0004 * Math.sin(dr * (2 * F + M));
    C1 = C1 - 0.0004 * Math.sin(dr * (2 * F - M)) - 0.0006 * Math.sin(dr * (2 * F + Mpr));
    C1 = C1 + 0.0010 * Math.sin(dr * (2 * F - Mpr)) + 0.0005 * Math.sin(dr * (2 * Mpr + M));
    const deltat = T < -11
      ? 0.001 + 0.000839 * T + 0.0002261 * T2 - 0.00000845 * T3 - 0.000000081 * T * T3
      : -0.000278 + 0.000265 * T + 0.000262 * T2;
    return jd1 + C1 - deltat;
  }
  function sunLongitude(jdn) {
    const T = (jdn - 2451545.0) / 36525, T2 = T * T, dr = PI / 180;
    const M = 357.52910 + 35999.05030 * T - 0.0001559 * T2 - 0.00000048 * T * T2;
    const L0 = 280.46645 + 36000.76983 * T + 0.0003032 * T2;
    let DL = (1.914600 - 0.004817 * T - 0.000014 * T2) * Math.sin(dr * M);
    DL += (0.019993 - 0.000101 * T) * Math.sin(dr * 2 * M) + 0.000290 * Math.sin(dr * 3 * M);
    let L = (L0 + DL) * dr;
    return L - PI * 2 * INT(L / (PI * 2));
  }
  const sunLong = (day) => INT(sunLongitude(day - 0.5 - TZ / 24) / PI * 6);
  const newMoonDay = (k) => INT(newMoon(k) + 0.5 + TZ / 24);
  function lunarMonth11(yy) {
    const k = INT((jdFromDate(31, 12, yy) - 2415021) / 29.530588853);
    const nm = newMoonDay(k);
    return sunLong(nm) >= 9 ? newMoonDay(k - 1) : nm;
  }
  function leapMonthOffset(a11) {
    const k = INT((a11 - 2415021.076998695) / 29.530588853 + 0.5);
    let last, i = 1, arc = sunLong(newMoonDay(k + i));
    do { last = arc; i++; arc = sunLong(newMoonDay(k + i)); } while (arc !== last && i < 14);
    return i - 1;
  }
  /** Solar (d, m, y) → [lunarDay, lunarMonth, lunarYear, leap(0|1)]. */
  function toLunar(dd, mm, yy) {
    const dayNumber = jdFromDate(dd, mm, yy);
    const k = INT((dayNumber - 2415021.076998695) / 29.530588853);
    let monthStart = newMoonDay(k + 1);
    if (monthStart > dayNumber) monthStart = newMoonDay(k);
    let a11 = lunarMonth11(yy), b11 = a11, lunarYear;
    if (a11 >= monthStart) { lunarYear = yy; a11 = lunarMonth11(yy - 1); }
    else { lunarYear = yy + 1; b11 = lunarMonth11(yy + 1); }
    const lunarDay = dayNumber - monthStart + 1, diff = INT((monthStart - a11) / 29);
    let leap = 0, lunarMonth = diff + 11;
    if (b11 - a11 > 365) {
      const leapDiff = leapMonthOffset(a11);
      if (diff >= leapDiff) { lunarMonth = diff + 10; if (diff === leapDiff) leap = 1; }
    }
    if (lunarMonth > 12) lunarMonth -= 12;
    if (lunarMonth >= 11 && diff < 4) lunarYear -= 1;
    return [lunarDay, lunarMonth, lunarYear, leap];
  }
  /** Lunar → solar [d, m, y]; [0,0,0] when the leap month does not exist. */
  function toSolar(ld, lm, ly, leap) {
    let a11, b11;
    if (lm < 11) { a11 = lunarMonth11(ly - 1); b11 = lunarMonth11(ly); }
    else { a11 = lunarMonth11(ly); b11 = lunarMonth11(ly + 1); }
    const k = INT(0.5 + (a11 - 2415021.076998695) / 29.530588853);
    let off = lm - 11; if (off < 0) off += 12;
    if (b11 - a11 > 365) {
      const leapOff = leapMonthOffset(a11);
      let leapMonth = leapOff - 2; if (leapMonth < 0) leapMonth += 12;
      if (leap && lm !== leapMonth) return [0, 0, 0];
      if (leap || off >= leapOff) off += 1;
    }
    return jdToDate(newMoonDay(k + off) + ld - 1);
  }

  const dateOf = ([d, m, y]) => new Date(y, m - 1, d);
  const startOfDay = (dt) => new Date(dt.getFullYear(), dt.getMonth(), dt.getDate());

  /** Next giỗ on/after `today`: always the regular (non-leap) month; day 30 falls back to 29 (spec §7). */
  function nextGio(day, month, today) {
    const t = startOfDay(today || new Date());
    const [, , ly] = toLunar(t.getDate(), t.getMonth() + 1, t.getFullYear());
    for (const y of [ly, ly + 1]) {
      let s = toSolar(day, month, y, 0);
      if (day === 30 && toLunar(s[0], s[1], s[2])[0] !== 30) s = toSolar(29, month, y, 0);
      const dt = dateOf(s);
      if (dt >= t) return { date: dt, days: Math.round((dt - t) / 86400000), lunarYear: y };
    }
    return null;
  }
  const MONTHS = ["", "tháng Giêng", "tháng Hai", "tháng Ba", "tháng Tư", "tháng Năm", "tháng Sáu",
    "tháng Bảy", "tháng Tám", "tháng Chín", "tháng Mười", "tháng Mười một", "tháng Chạp"];
  const WEEKDAYS = ["Chủ nhật", "Thứ hai", "Thứ ba", "Thứ tư", "Thứ năm", "Thứ sáu", "Thứ bảy"];
  const pad = (n) => String(n).padStart(2, "0");
  const lunarText = (d, m) => `${d <= 10 ? "mùng " + d : d} ${MONTHS[m]}`;
  const solarText = (dt) => `${WEEKDAYS[dt.getDay()]}, ${pad(dt.getDate())}/${pad(dt.getMonth() + 1)}/${dt.getFullYear()}`;

  /** Solar date of death derived from full lunar date (spec §2.4); null when the year is missing. */
  function deathSolar(ld) {
    if (!ld || !ld.d || !ld.m || !ld.y) return null;
    const s = toSolar(ld.d, ld.m, ld.y, ld.leap ? 1 : 0);
    return s[0] ? `${pad(s[0])}-${pad(s[1])}-${s[2]}` : null;
  }

  g.Lunar = { toLunar, toSolar, nextGio, lunarText, solarText, deathSolar, MONTHS, pad };
})(typeof window !== "undefined" ? window : globalThis);
