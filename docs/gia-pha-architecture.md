# Gia phả — kiến trúc và những cái bẫy

Tài liệu cho người sửa tính năng này về sau. Phần "bẫy" quan trọng hơn phần mô tả:
mỗi mục ở đó là một lỗi đã được chặn bằng test, gỡ ra là nó quay lại.

Hợp đồng dữ liệu cho backend (entity, bất biến quan hệ, đề xuất API): `docs/gia-pha-api-spec.md`.
File này nói **cách app đang chạy trên máy** — chưa có API, chưa có Redux.

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
khác bằng nền tím — không dùng viền nét đứt cho hai nghĩa đó.

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
`getLunarDate` / `getSolarDateSafe` — cả hai cùng đọc bảng tra TK nên round-trip đúng. Repo
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
- Nút gỡ vợ/chồng — `unlinkSpouse` có, form sửa chỉ **thêm** spouse, không gỡ.
- Xoá `local_memorials` + `src/types/memorial.ts` sau khi migration chạy thực địa vài bản.
