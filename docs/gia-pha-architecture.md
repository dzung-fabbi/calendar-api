# Gia phả — kiến trúc và những cái bẫy

Tài liệu cho người sửa tính năng này về sau. Phần "bẫy" quan trọng hơn phần mô tả:
mỗi mục ở đó là một lỗi đã được chặn bằng test, gỡ ra là nó quay lại.

Hợp đồng dữ liệu cho backend (entity, bất biến quan hệ, đề xuất API): `docs/gia-pha-api-spec.md`.
File này nói **cách app đang chạy trên máy** (MMKV, chưa Redux). Backend `/api/gia-pha/v1/family` **đã có** nhưng app chưa nối; kế hoạch nối và phần liên kết dòng họ ở hai mục cuối ("Nối API server", "Liên kết dòng họ").

## Bối cảnh

App bị App Store reject hai lần theo 4.3(b) (bị xếp vào nhóm app chiêm tinh). Toàn bộ
tính năng chọn ngày tốt và lá số tử vi đã bị **xoá khỏi source**. Tab thứ hai lần lượt là
Ngày Tốt → Giỗ → **Gia phả**. Tính năng "Giỗ" riêng đã bị gỡ: nhắc ngày giỗ giờ là một
Sự kiện có kiểu lặp *Hàng năm (Âm lịch)*.

## Các lớp

```
src/types/family.ts                  Person — chỉ lưu cạnh đi lên + vợ/chồng
src/utils/family-graph.ts            Engine thuần: dẫn xuất, kiểm toàn vẹn, tách cụm,
                                     ghost-spouse lúc vẽ. KHÔNG import relatives-tree
src/utils/family-tree-adapter.ts     File DUY NHẤT import relatives-tree
src/utils/family-layout.ts           Đơn vị thư viện → pixel, trả TreeLayout
src/utils/family-relationship-label.ts  Nhãn tập an toàn (trực hệ với "tôi")
src/utils/family-gender.ts           Default giới tính từ nhãn (migration + form)
src/services/family-storage.ts       CRUD MMKV + selfId + lineageOfId
src/services/family-relations.ts     NƠI DUY NHẤT ghi cạnh quan hệ
src/services/family-migration.ts     Giỗ cũ → Person + Sự kiện lặp âm; schema v2
src/screens/FamilyScreen/
  relative-link-rules.ts             Luật nối người lẻ + ứng viên ô Cha/Mẹ/Vợ
  canvas-transform.ts                Pinch/pan/fit, test được bằng số
  FamilyTreeScreen.tsx               Tab cây / danh sách; chọn cụm; dòng họ đang xem
  FamilyPersonFormScreen.tsx         Tạo/sửa + ghi quan hệ
  FamilyPersonDetailScreen.tsx       Đọc dẫn xuất + lối sang nhắc giỗ
  components/FamilyCanvas.tsx        Chỉ nhận TreeLayout; không biết Person[]
```

Ranh giới quan trọng nhất: `family-graph.ts` không biết `relatives-tree` tồn tại, và
`FamilyCanvas` chỉ nhận `TreeLayout`. Nhờ đó logic khó test được bằng jest thuần, và nếu
phải thay thư viện layout thì chỉ sửa `family-tree-adapter.ts`.

Nguồn sự thật là MMKV (`family_persons`, `family_self_id`, `family_lineage_of_id`). Màn
cây đọc lại mỗi lần focus. Không saga, không đồng bộ server.

## Quyết định mô hình

**Chỉ lưu `fatherId` / `motherId` / `spouses`.** `children` và `siblings` dẫn xuất mỗi lần
đọc. Anh–em là *sự kiện dẫn xuất* (chung ≥1 cha mẹ): lưu nó thì mỗi lần sửa cha mẹ làm hỏng
một tập bản ghi khác không cục bộ. n < 500 nên dựng `Map` mỗi lần đọc là miễn phí.

`PersonDraft` cố ý loại mọi trường quan hệ — sửa thông tin không đụng được cha/mẹ/vợ chồng.
Cạnh chỉ ghi qua `family-relations.ts`.

**Đồng-phụ-huynh (`coParents`) cũng dẫn xuất, không ghi xuống đĩa.** Thêm Cha rồi thêm Mẹ
cho cùng một người chỉ đặt hai ô, không sinh cạnh vợ chồng. "Có con chung" ≠ "đã cưới", mà
`SpouseLink` chỉ có `'married' | 'divorced'` — ghi bừa một trong hai là bịa. Lúc **vẽ**,
`toTreeNodes` vẫn nối họ thành cặp (thư viện chỉ hiểu `spouses`); lúc **đọc**, màn chi tiết
dùng `getPartners` = spouses tường minh + co-parents. Hai tầng phải nói cùng một chuyện.

**Nhãn xưng hô: suy tập an toàn, không suy tập mơ hồ.** Ô "Quan hệ với bạn" là quan hệ với
*"tôi"*, không phải với node được bấm.

Suy được (`family-relationship-label.ts`), và form **ghi đè** nhãn cũ lúc lưu khi đã nối
vào cây:

- Trực hệ đi lên, theo đường cha/mẹ: Cha, Mẹ, Ông/Bà nội, Ông/Bà ngoại. Đời cụ trở lên gộp
  `'Cụ / Tổ tiên'` — cụ nội / kỵ / can gọi khác nhau theo vùng.
- Trực hệ đi xuống theo số đời: Con, Cháu, Chắt, rồi `'Hậu duệ'`. Không phân nội/ngoại.
- Thêm từ đúng node "tôi": Cha, Mẹ, Con, Vợ/Chồng (Vợ/Chồng cần đã chọn giới tính).

Không suy: `anh/chị/em` (cần thứ tự sinh), `bác/chú/cô/dì/cậu`, `thím/mợ`, vợ của Cha
(chưa chắc là Mẹ), con của Ông nội (tuổi quyết bác/chú/cô). Suy ra sẽ sai một cách tự tin.

Người **chưa nối ai** thì tự chọn/tự nhập nhãn. Nhãn chỉ đúng một cạnh so với "tôi"
(`Cha`/`Mẹ`/`Ông bà nội ngoại`/`Vợ`/`Chồng`/`Con`/`Anh chị em`) thì `linkStandalone` ghi
cạnh đó sau khi tạo bản ghi. `Cụ / Tổ tiên`, `Cháu`, `Chắt`, `Hậu duệ`, nhãn tự nhập không
chỉ ra chỗ treo — vẫn lưu người, vào nhóm "chưa nối vào cây". Thiếu người trung gian (chưa
có Mẹ mà chọn Ông ngoại) **không chặn lưu**; form hiện dòng nhắc.

**`gender` là giá trị hạng nhất, không chỉ phục vụ layout.** `'unknown'` được phép everywhere.

| Chỗ dùng | Việc `gender` làm |
|---|---|
| `toTreeNodes` | `'unknown'` → `'male'` **chỉ** để thư viện xếp trái/phải trong một cặp. Tên/avatar lấy từ `Person`. |
| Thẻ cây, danh sách, chi tiết | Màu avatar nam/nữ/chưa rõ |
| `addRelative` / `linkChild` | `'female'` → ô mẹ; còn lại (kể cả `'unknown'`) → ô cha |
| Ứng viên Cha/Mẹ/Vợ | Ô cha loại `'female'`, ô mẹ loại `'male'`; vợ/chồng loại khi **cả hai đã biết** và trùng giới. `'unknown'` không bị loại. |
| Nhãn Vợ/Chồng | Suy từ giới tính người đang nhập |
| Tên cụm `"Nhà …"` | Hoà mọi tiêu chí khác thì ưu tiên nam |
| `inferGenderFromRelationship` | **Chỉ** default lúc migrate Giỗ cũ và điền sẵn ô form. User luôn sửa được. Chỗ mơ hồ (`em`, `con`, `bác`) → `'unknown'`. |

**"Tôi" là scalar** (`family_self_id`), không phải cờ `isSelf` trên bản ghi — một cờ có thể
`true` ở hai chỗ cùng lúc. Cây mặc định mở từ **tổ** của "tôi" (`getLineageRootId`: leo
`fatherId ?? motherId`, ưu tiên cha). Người lẻ (cụm size = 1) **không** vẽ thành cây một
node — sau migrate Giỗ cũ mọi bản ghi đều là ốc đảo; danh sách + "Nối vào cây" mới là việc
cần làm.

**Dòng họ đang xem** (`family_lineage_of_id`) lưu id **người được bấm** (chấm nhánh trên
thẻ), không lưu gốc cây. Gốc là dẫn xuất: thêm một đời tổ nữa là gốc đổi. Lưu gốc thì hôm
sau thêm cụ là trạng thái trỏ sai chỗ.

**`deceased` tường minh.** Không suy từ việc có ngày mất. Cụ tổ đã mất mà không nhớ ngày
vẫn `deceased: true`.

**Ngày mất gốc là âm lịch.** Form nhập âm; dương suy ra lúc lưu khi đủ ngày+tháng+năm.
Giỗ (`hasLunarDeath`) chỉ cần ngày+tháng âm, năm được thiếu. `deathTime` không tham gia
tính giỗ.

**Field có trong `Person` nhưng UI chưa ghi:** `birthOrder` (layout đã xếp theo nó →
`createdAt` → `id`), `fatherRel`/`motherRel` = `'adopted'`, `SpouseLink.type` = `'divorced'`.
Schema giữ; đường nối hiện vẽ **một nét liền** cho mọi loại (`TreeConnectors` một `<Path>`).

## Hai loại ô trống lúc vẽ

Cả hai **không persist**. Đừng nhầm.

1. **Placeholder thư viện** (`male-ph` / `female-ph`): `calcTree(..., { placeholders: true })`
   chỉ sinh ô cho **cha và mẹ của gốc**. Bấm = thêm đúng người đó. Không có ô cho vợ/chồng
   và con — hai cái đó do nút `+` trên mỗi thẻ.

2. **Ghost-spouse** (`ghost-spouse:{father|mother}:{personId}`): `toTreeNodes` chèn khi một
   người **đã có** vợ/chồng thật mà vẫn còn con khuyết bên kia. `relatives-tree` vẽ theo cặp
   rồi lọc con phải có trong `children` của **cả hai**; thiếu mẹ thì đứa con (và cả nhánh
   dưới) biến mất khỏi cây dù dữ liệu đúng. Ô này chỉ **giữ chỗ** (`GhostNode unknown`):
   thêm một bà vợ nữa không làm bà thành mẹ của những đứa đó — sửa ở từng người con.

Nét đứt trên cây **chỉ** nghĩa là ô trống. Người đã mất ghi `(đã mất)` bằng chữ, thẻ "tôi"
khác bằng nền tím — không dùng viền nét đứt cho hai nghĩa đó. Cây dòng họ đánh dấu "gia đình
bạn / sửa trực tiếp được" bằng **viền trong liền màu**, cũng **không** dùng nét đứt.

Mọi thẻ (thật và trống) cùng `width`/`height` (`DEFAULT_METRICS`). Layout thư viện giả định
mọi node cùng size; làm một thẻ to hơn là đường nối lệch.

## Bẫy — đã kiểm chứng trên source `relatives-tree@3.2.2`

| Bẫy | Hậu quả thật | Chặn ở đâu |
|---|---|---|
| `rootId` không có trong danh sách node | Ném `ReferenceError` **không có thông điệp** — gần như không lần ra từ crash report | `calcFamilyTree` guard trước khi gọi |
| id trỏ vào người không tồn tại | `TypeError: Cannot read properties of undefined` — crash, không phải vẽ sai | `buildFamilyIndex` lọc, `toTreeNodes` không sinh id treo |
| Chu trình cha–con | Đệ quy vô hạn, **TREO JS thread** (app đơ, không log) | `canSetParent` chặn khi ghi + `buildFamilyIndex` cắt khi đọc |
| Con chỉ có trong `children` của MỘT cha mẹ | Con **biến mất khỏi cây** mà không báo lỗi | Dẫn xuất `children` nên lệch hai phía không tồn tại được |
| Người đã có vợ/chồng + con khuyết bên kia | Thư viện lọc con theo cặp → con và nhánh dưới **biến mất** | `addGhostSpouses` lúc vẽ; `linkSpouse` điền ô trống **chỉ khi vợ/chồng đầu tiên** |
| Hai cha mẹ chung con, chưa nối hôn | Thư viện không nối cặp → mẹ không phải hậu duệ của gốc nên **biến mất** | `toTreeNodes` thêm co-parent vào `spouses` lúc vẽ, không ghi đĩa |
| `const enum Gender/RelType` + `isolatedModules` | Lỗi biên dịch | Ép kiểu đúng một chỗ trong adapter |
| Package chỉ có bản ESM, import không đuôi file | Test chết "Cannot use import statement" | `transformIgnorePatterns` trong `jest.config.js` |
| Gỡ vợ/chồng chỉ một bên | Bản đọc hợp nhất hai chiều nên nối lại | `unlinkSpouse` xoá cả hai bên. UI hiện **không có nút gỡ**; chỉ clear cha/mẹ lúc sửa, hoặc xoá người |
| Đổi id khi migrate | Bỏ rơi nhắc đã đặt (`<id>#<remind>#<lần>`) → nhắc trùng mãi mãi | Migration giữ nguyên id + huỷ hàng đợi `gio_*` |
| Tin mỗi `gioEventId` | Xoá sự kiện ở tab Sự kiện không dọn field → nút "Xem nhắc" mở màn không còn sự kiện, hết đường đặt lại | Chi tiết người `getEventById` lại; id treo coi như chưa đặt |
| Lưu gốc cây thay vì người được bấm | Thêm một đời tổ là trạng thái xem trỏ sai nhánh | `family_lineage_of_id` = id thẻ được bấm; gốc = `getLineageRootId` |
| `key={treeId}` trên canvas | Remount mất số đo khung nhìn; cây mới vẽ 1:1 rồi mới fit, nhảy một nhịp | `FamilyCanvas` nhận `treeId` qua prop, không unmount |
| Gắn pinch/pan vào view đang `transform` | Gesture-handler trả toạ độ cây (đã chia cho scale); tiêu điểm pinch lệch, kéo bị chậm theo zoom | Detector bọc lớp phủ **không** transform, kín khung nhìn |
| App và server dùng hai nguồn âm lịch khác nhau | Giỗ nhắc lệch một ngày (có năm lệch một tháng) giữa máy và FCM dòng họ, không lỗi nào báo | Một nguồn: Hồ Ngọc Đức UTC+7; test vector spec §7.0 ở cả hai phía |
| `ZOOM_MIN` cứng 0.4 | Cây đông người có mức fit < 0.4 → chụm hết cỡ vẫn không thấy cả cây | `minZoom` = `min(ZOOM_MIN, fitZoom)` |

**Đơn vị toạ độ thư viện:** một node rộng/cao đúng 2 đơn vị (`UNITS_PER_NODE = 2`),
`left`/`top` là mép trên trái, connector đi qua **tâm** node. Đổi sang pixel phải cộng nửa
khoảng cách vào mép node thì tâm mới trùng đầu mút đường nối — xem `family-layout.ts`.

**Cha dượng / mẹ kế không vào ô cha/mẹ thứ hai.** Ô cha/mẹ tối đa một người. `addRelative`
từ chối cha/mẹ lần 2. Cha dượng = vợ/chồng của mẹ. Muốn thay cha đang có: `clearFather`
rồi mới `setFather` — `linkChild` không đè ô đã chiếm (`PARENT_SLOT_TAKEN`).

**Thêm anh chị em khi chưa có cha và chưa có mẹ → từ chối.** Không bịa cha mẹ ẩn để gom
anh em; `siblings` chỉ dẫn xuất được khi có ít nhất một cạnh cha/mẹ thật.

**Xoá không lan.** Xoá ông không xoá nhà, không tự nối cháu lên ông. Con cháu rơi xuống
"chưa nối vào cây". Nếu người đó là "tôi" → `selfId = null`. Sự kiện giỗ **không** bị xoá
theo — `gioEventId` đứt, event vẫn trong tab Sự kiện.

## Lặp hằng năm theo âm lịch

`src/utils/lunar-recurrence.ts` (trước đây là `gio-anniversary.ts`). Dùng cặp
`getLunarDate` / `getSolarDateSafe` — cả hai cùng đọc bảng tra TK nên round-trip đúng.

> **Cần chốt trước khi nối API** (spec §7.0): backend tính âm lịch bằng Hồ Ngọc Đức **UTC+7**
> (`giapha/services/vn_lunar.py`). Nếu bảng TK của app là lịch Trung Quốc (UTC+8) thì app và
> server lệch ở 462 tháng trong 1900–2100 — gần nhất 2030 tháng Giêng, 2031 tháng 3 nhuận,
> 2032 tháng 2. Nhắc giỗ local (Notifee) và `solarDeathDate` / nhắc giỗ dòng họ (server) sẽ
> khác ngày. Kiểm bằng vector §7.0: `21/01/1985` phải là mùng 1 Tết, không phải mùng 1 tháng Chạp. Repo
còn cặp `convertSolar2Lunar` / `convertLunar2Solar` tính theo thiên văn và `date-chinese`;
**trộn các họ này với nhau lệch tới một tháng.**

Hai quy tắc nghiệp vụ:

- Mốc ngày 30 mà năm đó tháng thiếu 29 ngày → lùi về ngày cuối tháng, **không** dồn sang
  mùng 1 tháng sau (dồn là sai hẳn tháng cúng).
- Mốc rơi vào tháng nhuận → cúng theo tháng thường. `lunarLeap` chỉ để hiển thị.

Nối vào Sự kiện qua `RepeatType = 5` trong `event-notification.ts`. Kiểu 5 **bắt buộc** có
`lunarDate`; thiếu thì không đặt lịch nào chứ không rơi về một mốc dương lẻ loi — nhắc sai
ngày trong im lặng còn tệ hơn không nhắc.

Từ màn chi tiết người đã mất có ngày+tháng âm: mở form sự kiện với tên `"Giỗ {tên}"`,
`presetRepeatType = 5`, `linkPersonId` → lưu xong ghi `gioEventId`. Thiếu năm mất thì mồi
ngày dương bằng `getSolarAnchorForLunar` (năm nào có đúng ngày âm đó), vì form sự kiện
thiếu ngày sẽ mặc định hôm nay.

## Migration

`FAMILY_SCHEMA_VERSION = 2`. Cửa theo số (`from < 1`, `from < 2`), không một cờ tất-cả:

1. Nhập `local_memorials` → `Person` đã mất, giữ nguyên id; nếu có nhắc thì tạo Sự kiện
   lặp âm. Chạy lại bước này sẽ hồi sinh người user đã xoá — vì vậy cờ version bắt buộc.
2. Lấp ô cha/mẹ trống bằng vợ/chồng **duy nhất** (dữ liệu nhập con trước, vợ sau, trước
   khi `linkSpouse` tự điền).

`local_memorials` đóng băng: không ghi nữa, chưa xoá (build cũ trên máy còn đọc).

## Còn nợ

- Nét đứt riêng cho con nuôi / ly hôn (field đã lưu, `TreeConnectors` vẫn một nét liền).
- Ảo hoá node khi cây vượt ~200 người (hiện `FamilyCanvas` render hết; `TreeLayout` đã có
  rect từng node nên cắt theo khung nhìn là đủ).
- UI nhập `birthOrder` — layout đã xếp theo field này, form chưa có ô.
- Nút gỡ vợ/chồng — `unlinkSpouse` có (server: `POST /relations/unlink-spouse`), form sửa chỉ **thêm** spouse, không gỡ. Mockup/prototype đã có nút "Gỡ".
- Nối API server (mục dưới) + màn "Đưa gia phả lên tài khoản" (import một lần).
- Liên kết dòng họ và quyền dòng họ (mục dưới) — theo plan `260919-shared-clan-tree-collaboration`.
- Xoá `local_memorials` + `src/types/memorial.ts` sau khi migration chạy thực địa vài bản.

## Nối API server (kế hoạch)

Hợp đồng: `docs/gia-pha-api-spec.md` §8 (đã triển khai), §12 (import). Thứ tự khi bật:

1. **Import một lần** (`PUT /v1/family/import`) cho máy đã có dữ liệu: hỏi đồng ý → gửi
   snapshot schema v2 → dùng `idMap` đổi id → giữ MMKV làm dự phòng tới khi đổi xong.
   Máy trống: CRUD thẳng server.
2. **Nguồn sự thật là server.** `family-storage.ts` thay bằng client API. MMKV còn là cache
   đọc offline; v1 **không** ghi offline (hiện "Không có mạng, chỉ xem") — tránh phải gộp.
   **Đã chốt 2026-09-19.** Nút thêm/sửa/xoá khoá khi mất mạng; nhắc giỗ local vẫn chạy.
3. **Mỗi thao tác UI = một endpoint** (§8.3). Sau mutation, **thay cả danh sách** bằng
   `persons[]` server trả; không vá cục bộ, để dẫn xuất (con, anh em, cụm) không lệch.
4. `family-relations.ts` / `relative-link-rules.ts` giữ làm **kiểm tra trước** (khoá nút,
   lọc ứng viên). Server là trọng tài: luôn hiện nguyên `error.message` / `warning.message`.
5. `family_self_id` → `selfId` của server. `family_lineage_of_id` vẫn là state máy.
6. Sự kiện giỗ **vẫn local** (Notifee); tạo xong gọi `PUT /persons/{id}/gio-event`. Xoá người
   không xoá sự kiện (server cũng giữ), chi tiết người vẫn tra lại sự kiện còn không.
7. Mọi bẫy ở trên (layout, ghost-spouse, chu trình) vẫn đúng: layout là việc của client.

## Liên kết dòng họ (kế hoạch)

Spec §14–§15; mockup `plans/visuals/gia-pha-app-mockup.html`; bản dùng thử
`plans/visuals/gia-pha-prototype/` (có ghi API mỗi thao tác).

- **Một engine cho hai loại cây.** `/clans/{id}/tree` trả node/edge với field tiếng Việt
  (`ho_ten`, `gioi_tinh`, `death_lunar_*`, `Marriage.status`). Thêm **một** adapter
  `clan-tree-adapter.ts` đổi sang `Person` rồi dùng lại `family-graph.ts` +
  `family-tree-adapter.ts`. Không viết engine thứ hai. `Marriage.status`: `ly_hon` →
  `divorced`, `dang_ket_hon` / `goa` → `married`.
- **Người đã liên kết** (`linked: true`): dấu 🔗 trên thẻ; form sửa ghi "🔗 từ {họ}" cạnh
  field chung (tên, giới tính, đã mất, ngày sinh, ngày mất âm); lưu xong đọc `clanWrites`
  và báo **từng họ**: đã cập nhật / đã gửi đề xuất / xung đột (409, hiện giá trị mới nhất).
- **Quyền lấy từ server**, không tự tính: `my_editable_ids` (viền "gia đình bạn"),
  `can_edit` (nút "Sửa" hay "Đề xuất sửa"). Luật phạm vi (anh chị em chưa được nhận, trưởng
  chi…) chỉ sống ở server.
- **Không tự sửa cấu trúc** theo họ: màn chi tiết hiện khác biệt (`/links/diff`), user tự
  quyết. Tách liên kết chép giá trị hiện tại về cây riêng.
- Ghép gợi ý chỉ là gợi ý: mặc định chọn sẵn cặp "Chắc", cặp "Có thể" để user tick.

## Mô hình quyền (Phase 1, 6)

**Phạm vi gia đình** (`family_scope`): người P có quyền sửa người trong tập {P} ∪ vợ/chồng(P) ∪ cha,mẹ(P) ∪ hậu duệ(P) ∪ vợ/chồng hậu duệ **chỉ khi** những người đó chưa được xác minh (node chưa có `ClanMember.person_verified`). Anh chị em ruột (chung ≥1 cha/mẹ) vào phạm vi **chỉ** khi chưa có binding xác minh của họ ở họ.

**Phạm vi chi** (Phase 6): editor có `scope_root_person_id` → cộng hậu duệ(root) ∪ {root} ∪ vợ/chồng hậu duệ. Hợp với phạm vi gia đình nếu có binding xác minh. Owner/manager: toàn họ (scope_root = null).

**Phạm vi mời** (downward only): role viewer → mời chỉ người trong phạm vi ghi của mình (gia đình hoặc chi); role editor → toàn họ; role manager → toàn họ; owner → toàn họ. Ngoài phạm vi → yêu cầu duyệt.

Kiểm quyền **ở bước tạo CR hoặc thao tác**. `permissions_scope.can_write_persons(member, clan_id, person_ids)` → xoá ids ngoài phạm vi, phần còn lại phép ghi. Nếu trống → 403. Thay vì từ chối lô bulk, các loại yêu cầu duyệt từng người ngoài phạm vi tạo từng CR.

## Đề xuất thay đổi (Phase 2)

Model `ChangeRequest`: `clan`, `proposer`, `target_person`, `target_marriage`, `action` (create/update/delete_person/create/update/delete_marriage), `payload_json` (serializer ghi validate), `status` (pending/approved/rejected/expired/withdrawn/stale), `base_version`, `reviewer`, `review_note`.

**Vòng đời:**
- Tạo: status = pending, hoặc active ngay (duyệt đã tạo ngoài phạm vi, role không đủ)
- Ngày 7: push nhắc người duyệt (1 lần)
- Ngày 30: hết hạn → status = expired, push người gửi ("gửi lại được")
- Duyệt: target bị đổi sau `base_version` → 409 stale, `override_stale=true` → bỏ qua
  - Áp qua `services.person_write` / `services.marriage_write` (cùng đường ghi thực)
  - Tạo `PersonRevision` với `change_request_id`
  - Tăng `Person.version` (bước an toàn lượt lượt)
  - Push người gửi kết quả
- Từ chối: status = rejected, push người gửi lý do
- Withdraw: proposer khi pending → status = withdrawn

**Management command** `expire_change_requests` (chạy hằng ngày, cùng cron giỗ):
- Ngày 7 (pending): push owner + manager
- Ngày 30 (pending): status → expired, push proposer
- Idempotent

Giới hạn: 20 pending / proposer / họ; throttle POST 20/day.

## Liên kết cá nhân ↔ dòng họ (Phase 4)

Model `FamilyPersonLink(family, family_person, clan, clan_person)`: **không đồng bộ**, là tham chiếu duy nhất chiều.

**Field chung (overlay):** name, gender, deceased (mới: `Person.da_mat`), solarBirthDate, solarDeathDate, lunarDeathDay/Month/Year/Leap. Được đọc thẳng từ họ lúc `GET /v1/family`, được đó lưu giá trị hiện tại vào `FamilyPerson` khi tách.

**Field riêng (giữ ở cá nhân):** relationship, note, gioEventId, birthTime, deathTime.

**Ghép gợi ý** (`services/family_clan_matching.py`):
- Neo: selfId người ↔ binding họ (nếu có)
- Lan theo cấu trúc: cha↔cha, mẹ↔mẹ, vợ/chồng, con trùng tên chuẩn hoá
- Còn lại: tên bỏ dấu + **năm sinh phải trùng** (dùng `vn_lunar` chuyển đổi)
- Không bao giờ tự link

**Tách** (`services/family_link_detach.py`): snapshot field chung vào `FamilyPerson` (bảo toàn giá trị lúc link), xoá `FamilyPersonLink`. Tự động khi: rời họ, xoá khỏi họ, họ bị soft-delete, hoặc clan_person bị soft-delete.

**Query**: `GET /v1/family` thêm +1 query (links JOIN field chung của clan person). Overlay lúc serialization, không thêm bước.

## Import từ máy (Phase 3)

`PUT /v1/family/import` (idempotent qua `importKey`):
- **Chỉ khi server rỗng** (0 người). Có dữ liệu + importKey khác → 409
- **Cá nhân luôn vào**, cạnh bị lỗi → bỏ + báo `skippedEdges`
- Field normalize: tên rỗng → "Chưa đặt tên"; > 60 ký → cắt; ngày sai → null
- Cạnh: bỏ nếu dangling, self, chu trình, sai giới tính ô, spouse unidirectional
- Thứ tự xét cạnh cố định (theo createdAt → id)
- Legacy id → `FamilyPerson.legacy_id` để retry idempotent
- Response: `idMap`, `selfId`, `persons`, `skippedEdges`, `warnings`
- Throttle: 5/hour

## Optimistic lock (Phase 5)

`Person.version` (clan): tăng ở **mỗi** PATCH, restore, approve CR, photo confirm/delete. Tăng bằng `F('version')+1` trong cùng `update()`.

`PATCH /clans/{id}/persons/{pid}` + body `version?`: nếu gửi và lệch → 409 `VERSION_CONFLICT` + trả `current`. Không gửi → như cũ (tương thích ngược).

`ChangeRequest.base_version` (thay thế `base_updated_at`): lưu version lúc tạo CR, lúc duyệt check xem target có đổi (so `base_version` vs hiện tại).

`PATCH /v1/family/persons/{id}` (linked person) + `clanVersions{clanId: n}?`: gửi version từ client cho **mỗi** họ đã link
- Nếu version match → áp thẳng qua `person_write` (ghi field chung)
- Nếu lệch → 409 conflict, trả `current` version, **không** tạo CR
- Nếu không quyền → tạo CR với `base_version` hiện tại
- Response: `clanWrites: [{clanId, result: 'applied'|'proposed'|'conflict', current?}]`
