# Gia phả — hợp đồng dữ liệu cho Backend

Tài liệu cho BE thiết kế API **khớp đúng logic app hiện tại**. Nguồn sự thật là code, không phải mô hình giả định:

- Kiểu: `src/types/family.ts`, `src/types/event.ts`
- Ghi dữ liệu: `src/services/family-storage.ts`, `src/services/family-relations.ts`
- Luật đồ thị: `src/utils/family-graph.ts`, `src/screens/FamilyScreen/relative-link-rules.ts`
- Form / chi tiết: `src/screens/FamilyScreen/FamilyPersonFormScreen.tsx`, `FamilyPersonDetailScreen.tsx`

Kiến trúc vẽ cây (layout, pinch/zoom) **không** thuộc phạm vi API — xem `docs/gia-pha-architecture.md`.

> **Trạng thái (cập nhật 2026-09-19)**
> - §1–§11: **đã triển khai** ở backend — 13 endpoint `/api/gia-pha/v1/family/*` (commit `b0e51e7`). Request/response và mã lỗi thực tế: `docs/api-reference.md` → "Gia Phả Cá Nhân". App **chưa** nối API (vẫn MMKV).
> - §12 (nhập từ máy), §14 (liên kết dòng họ), §15 (quyền trong dòng họ): **đã chốt, chưa làm** — plan `plans/260919-shared-clan-tree-collaboration/` (phase 1–6). Mục chưa làm ghi **[Planned · phase N]**.
> - §7.0: **xung đột cần chốt** giữa nguồn âm lịch của app và backend.

---

## 1. Trạng thái hiện tại

Backend **đã có API** (§8) nhưng app **chưa nối**. Hiện toàn bộ nằm local MMKV trên máy:

| Key | Nội dung |
|---|---|
| `family_persons` | JSON `Person[]` — nguồn sự thật |
| `family_self_id` | id người được đánh dấu "tôi" |
| `family_lineage_of_id` | id người đang xem theo dòng họ (UI, không bắt buộc sync) |
| `local_events` | JSON sự kiện (gồm nhắc giỗ) |

Không gắn với tài khoản đăng nhập. Xoá tài khoản Firebase **không** xoá gia phả trên máy (đang ghi trong chính sách quyền riêng tư). Khi đưa lên server: **một user = một gia phả**, và cần cập nhật chính sách quyền riêng tư vì dữ liệu hiện được cam kết "không rời khỏi máy".

Quy mô thực tế: người dùng tự nhập, **< 500 người**. Không cần phân trang phức tạp; `GET` cả cây là đủ. Trần cứng server: `FAMILY_MAX_PERSONS = 1000` (`settings.py`), vượt → `FAMILY_FULL`.

Người dùng cũ chuyển dữ liệu máy lên server một lần qua `PUT /v1/family/import` (§12). Trước khi gọi, app **phải hỏi đồng ý**, và chính sách quyền riêng tư phải được cập nhật trước khi bật tính năng (chủ sản phẩm phụ trách — chốt 2026-09-19).

Mất mạng: app **chỉ xem** từ cache, không cho thêm/sửa/xoá (chốt 2026-09-19) — server là nguồn sự thật, không có hàng đợi ghi offline để gộp.

---

## 2. Nguyên tắc mô hình — BE phải giữ nguyên

### 2.1 Chỉ lưu cạnh đi lên + vợ/chồng

Mỗi người lưu:

- `fatherId` / `motherId` (tối đa **một** cha, **một** mẹ)
- `spouses[]` (nhiều vợ/chồng được)

**Không lưu** `children` và `siblings`. Hai thứ đó là dẫn xuất:

- Anh chị em = chung ≥ 1 cha hoặc mẹ đã biết
- Con của A = mọi người có `fatherId = A` hoặc `motherId = A`

Lưu `children`/`siblings` thì mỗi lần sửa cha mẹ làm hỏng một tập bản ghi khác không cục bộ. App dựng `Map` mỗi lần đọc.

### 2.2 "Tôi" là scalar, không phải cờ trên bản ghi

`selfId` lưu riêng, **đúng một người** (hoặc `null`). Không dùng `isSelf: boolean` trên Person — hai bản ghi có thể cùng `true`.

Cây mặc định mở từ **tổ xa nhất** tính từ "tôi", leo ưu tiên cha (gia phả Việt theo dòng cha); hết cha thì bước sang mẹ. Xem `getLineageRootId`.

### 2.3 `deceased` tường minh

Không suy "đã mất" từ việc có ngày mất. Cụ tổ đã mất mà không nhớ ngày vẫn `deceased: true` và không có `lunarDeath*`.

### 2.4 Ngày mất gốc là ÂM lịch

Người dùng nhập ngày mất theo âm. Ngày dương **suy ra lúc lưu** khi đủ ngày + tháng + năm âm.

Giỗ chỉ cần **ngày + tháng âm**. Năm có thể thiếu ("hai mươi tháng Chạp"). Thiếu năm thì **không** suy được ngày dương tương ứng (cùng ngày âm rơi khác chỗ mỗi năm).

### 2.5 Vợ/chồng đối xứng hai chiều

Ghi / gỡ phải **cả hai bên trong một transaction**. App đọc thì hợp nhất hai chiều: chỉ ghi một bên trông vẫn đúng, gỡ một bên sẽ bị nối lại.

### 2.6 Xoá không lan

Xoá một người:

- Xoá bản ghi đó
- Gỡ mọi `fatherId` / `motherId` / `spouses` trỏ tới họ
- **Không** xoá con cháu
- **Không** tự nối cháu lên ông
- Nếu người đó là "tôi" → `selfId = null`

Con cháu rơi xuống nhóm "chưa nối vào cây".

---

## 3. Entity

### 3.1 `Person`

App hiện sinh id client: `fam_<base36 timestamp>_<6 ký tự random>`. BE nên sinh UUID/ULID; app sẽ đổi sang id server khi wire API.

```ts
type PersonId = string; // UUID
type Gender = 'male' | 'female' | 'unknown';
type ParentRel = 'blood' | 'adopted';   // mặc định 'blood' khi vắng
type SpouseRel = 'married' | 'divorced'; // mặc định 'married'

type SpouseLink = { id: PersonId; type: SpouseRel };

type Person = {
  id: PersonId;
  name: string;                 // bắt buộc, trim, max 60
  gender: Gender;               // bắt buộc, được phép 'unknown'
  deceased: boolean;            // bắt buộc, mặc định false

  fatherId?: PersonId | null;
  motherId?: PersonId | null;
  fatherRel?: ParentRel | null; // chỉ ghi khi 'adopted'
  motherRel?: ParentRel | null;

  spouses: SpouseLink[];        // luôn là mảng, có thể []

  solarBirthDate?: string | null; // "DD-MM-YYYY"
  birthTime?: string | null;      // "HH:mm" 24h, tách khỏi ngày
  birthOrder?: number | null;     // 1 = con cả; UI hiện CHƯA nhập

  solarDeathDate?: string | null; // "DD-MM-YYYY", suy từ âm khi đủ năm
  deathTime?: string | null;      // "HH:mm" — KHÔNG ảnh hưởng ngày giỗ
  lunarDeathDay?: number | null;  // 1–30
  lunarDeathMonth?: number | null;// 1–12
  lunarDeathYear?: number | null; // có thể thiếu; server nhận 1800–2199 (giới hạn vn_lunar)
  lunarLeap?: boolean | null;     // tháng nhuận; giỗ vẫn cúng tháng thường

  relationship?: string | null;   // nhãn với "tôi", max 24, lưu CHỮ không phải enum id
  note?: string | null;           // max 500
  phone?: string | null;          // max 20, chuỗi tự do ("+84…", số bàn có dấu cách / gạch)
  education?: string | null;      // max 40 — học vấn
  occupation?: string | null;     // max 40 — nghề nghiệp
  gioEventId?: string | null;     // id sự kiện nhắc giỗ: chuỗi mờ ≤ 64 ký tự, KHÔNG phải UUID (giữ cả id cũ `gio_*`)

  createdAt: number;              // epoch ms
  updatedAt: number;              // epoch ms
};
```

**Ràng buộc field**

| Field | Rule |
|---|---|
| `name` | bắt buộc, trim, 1–60 ký tự. App chỉ chặn tên trống. |
| `gender` | `'male' \| 'female' \| 'unknown'` |
| `deceased` | boolean |
| Ngày dương | `"DD-MM-YYYY"` (zero-pad). Năm sinh picker từ **1800**. |
| Giờ | `"HH:mm"` đủ 2 phần mới lưu; chuỗi dở (`"08"`) bị loại. |
| `lunarDeathDay/Month` | chỉ có nghĩa khi `deceased === true`. Ngày 1–30, tháng 1–12. |
| `relationship` | nhãn tiếng Việt, **không** phải id. Danh sách gợi ý dưới đây; user có thể tự nhập. |
| `gioEventId` | optional. Xoá sự kiện **không** dọn field này — app luôn tra lại sự kiện còn tồn tại không. |
| `note`, `phone`, `education`, `occupation` | optional, trim; `""`/`null` = xoá. Giới hạn 500 / 20 / 40 / 40 (khớp `NOTE/PHONE/EDUCATION/OCCUPATION_MAX_LENGTH` của app). Quá dài → 400 `VALIDATION`; import thì cắt + `warnings`. Field **riêng** (§14.2). |

**Nhãn quan hệ gợi ý** (lưu `name`, không lưu `id`):

`Ông nội`, `Bà nội`, `Ông ngoại`, `Bà ngoại`, `Cha`, `Mẹ`, `Chồng`, `Vợ`, `Anh`, `Chị`, `Em`, `Con`, `Cụ / Tổ tiên`, `Cháu`, `Chắt`, `Hậu duệ`, hoặc chuỗi tự nhập.

Nhãn là **ghi chú với "tôi"**, không phải cạnh đồ thị. Đồ thị chỉ có cha/mẹ/vợ-chồng.

**Field có trong model nhưng UI chưa ghi**

- `birthOrder` — layout xếp con theo `birthOrder` → `createdAt` → `id`. Hiện luôn `undefined` nên xếp theo lúc tạo.
- `fatherRel` / `motherRel` = `'adopted'` — UI luôn để mặc định `'blood'`.
- `SpouseLink.type` = `'divorced'` — UI luôn ghi `'married'`.

Giữ schema; đừng bỏ. UI sẽ dùng sau (nét đứt con nuôi / ly hôn).

### 3.2 Family meta

```ts
type FamilyMeta = {
  selfId: PersonId | null;
};
```

`lineageOfId` là trạng thái xem UI (nhánh đang đứng), không cần persist server trừ khi muốn nhớ giữa các thiết bị.

### 3.3 Sự kiện nhắc giỗ (`LocalEvent`)

**Chốt:** sự kiện **ở lại trên máy** (Notifee đặt lịch local). Server không lưu `Event`, chỉ lưu `gioEventId` như chuỗi mờ qua `PUT /v1/family/persons/{id}/gio-event`. Không có `/v1/events` (phương án đầu của §8.5 **không** làm). Hệ quả: đổi máy thì nhắc giỗ cá nhân phải đặt lại. Nhắc giỗ **dòng họ** do server đẩy FCM (`gio_remind`, theo binding "tôi là ai") — hai đường độc lập, không trùng nhau vì hai nguồn dữ liệu khác nhau.

Giỗ **không** còn entity riêng. Là một sự kiện thường, gắn vào người qua `Person.gioEventId`.

```ts
type RepeatType = 0 | 1 | 2 | 3 | 4 | 5;
// 0 không lặp, 1 ngày, 2 tuần, 3 tháng, 4 năm dương, 5 năm ÂM

type RemindType = 0 | 1 | 2 | 3;
// 0 khi diễn ra, 1 trước 1 ngày, 2 trước 3 ngày, 3 trước 7 ngày

type Event = {
  id: string;
  name: string;                 // max 100; giỗ mặc định "Giỗ {tên}"
  solarDate: string;            // "DD-MM-YYYY" luôn có
  lunarDate?: string | null;    // "DD-MM-YYYY" âm; RepeatType=5 BẮT BUỘC có
  repeatType: RepeatType;
  remindBefore: RemindType[];   // không rỗng lúc lưu
  createdAt: number;
  updatedAt: number;
};
```

Từ màn chi tiết người đã mất có ngày+tháng âm, app mở form sự kiện với:

- `presetName = "Giỗ {name}"`
- `presetRepeatType = 5`
- `linkPersonId = person.id` → sau khi lưu, ghi `gioEventId`

Một người **tối đa một** sự kiện giỗ theo app hiện tại (`gioEventId` là scalar).

---

## 4. Luật quan hệ (bắt buộc trên server)

Mọi API sửa `fatherId` / `motherId` / `spouses` phải kiểm các luật này. App từ chối ghi nếu vi phạm; API trả 4xx kèm `code` + `message` tiếng Việt.

### 4.1 Mã lỗi (`IssueCode`)

| code | Khi nào | Chặn ghi? |
|---|---|---|
| `SELF_PARENT` | A là cha/mẹ của A; hoặc thêm cha/mẹ khi ô đã có người khác | Có |
| `SELF_SPOUSE` | A nối vợ/chồng với A | Có |
| `PARENT_CYCLE` | Người sắp làm cha/mẹ đang là con cháu của đứa con | Có |
| `PARENT_SLOT_TAKEN` | Ô cha (hoặc mẹ) đã có người khác. Muốn thay phải gỡ trước | Có |
| `DANGLING_FATHER` / `DANGLING_MOTHER` / `DANGLING_SPOUSE` | id trỏ người không tồn tại | Có |
| `DUPLICATE_ID` | Trùng id (validate, không phải mutation) | — |
| `SPOUSE_IS_ANCESTOR` | Hai người đang trực hệ (ông–cháu, cha–con…) | **Cảnh báo**, vẫn cho ghi |

**Mã server trả thêm** (đã triển khai; app hiển thị nguyên `message`):

| code | Khi nào | HTTP |
|---|---|---|
| `PARENT_SLOT_TAKEN` (message riêng cho ô cha / ô mẹ) | Ô đã có người; message gợi ý "cha dượng = vợ/chồng của mẹ" | 400 |
| `GENDER_MISMATCH` | Nam vào ô mẹ / nữ vào ô cha (server lọc như UI, §4.2) | 400 |
| `NO_PARENT_FOR_SIBLING` | Thêm anh chị em khi chưa có cha **và** mẹ | 400 |
| `SELF_ALREADY_SET` | `PUT /self` khi đã có "tôi" khác | 400 |
| `OTHER_PARENT_NOT_CANDIDATE` | `otherParentId` không thuộc partners hợp lệ → ô còn lại để trống | 200 (warning) |
| `FAMILY_FULL` | Vượt `FAMILY_MAX_PERSONS` | 400 |
| `PERSON_NOT_FOUND` | id không thuộc gia phả của user | 404 |
| `VALIDATION` | Field sai (tên rỗng, ngày sai định dạng…), kèm `fields` | 400 |

Cha dượng / mẹ kế **không** vào ô cha/mẹ thứ hai. Mô hình: vợ/chồng của mẹ (hoặc cha). App báo: *"Người này đã có cha. Cha dượng nên nhập là vợ/chồng của mẹ."*

### 4.2 Đặt cha / mẹ (`setFather` / `setMother`)

Input: `childId`, `parentId`, `rel?: 'blood' | 'adopted'` (default `'blood'`).

Chặn khi:

1. `childId === parentId`
2. `childId` nằm trong tổ tiên của `parentId` (chu trình)
3. Người không tồn tại

Không chặn giới tính ở tầng ghi (UI lọc: ô cha loại `'female'`, ô mẹ loại `'male'`; `'unknown'` vẫn hợp). BE nên lọc giống UI để client cũ/bug không ghi nam vào ô mẹ.

### 4.3 Gỡ cha / mẹ (`clearFather` / `clearMother`)

Xóa field tương ứng trên con. Không đụng người bị gỡ. Không nối lại tự động.

### 4.4 Nối vợ/chồng (`linkSpouse`)

Input: `aId`, `bId`, `type?: 'married' | 'divorced'` (default `'married'`).

- Ghi **cả hai** `spouses[]` (upsert theo id đối phương).
- Chỉ `SELF_SPOUSE` chặn. `SPOUSE_IS_ANCESTOR` trả kèm warning, vẫn lưu.

**Side-effect quan trọng — điền ô cha/mẹ trống của con sẵn có**, nhưng **chỉ khi đây là vợ/chồng ĐẦU TIÊN** của người đang có con:

- Người dùng hay nhập con trước, rồi mới thêm vợ. Nếu không điền, thư viện vẽ cặp không có con chung → **cả nhánh dưới biến mất khỏi cây**.
- Từ người thứ hai trở đi **không đoán** (con nào của bà nào chỉ user biết).

Giới tính phải hợp ô: nam không vào `motherId`, nữ không vào `fatherId`. `'unknown'` được.

UI **không** lọc hôn nhân đồng giới khi một bên `'unknown'`; khi **cả hai đã biết** và trùng giới tính thì không mời. Gia phả Việt không ghi hôn nhân đồng giới.

### 4.5 Gỡ vợ/chồng (`unlinkSpouse`)

Xóa link **cả hai bên**. App hiện **không có nút gỡ** trên UI (chỉ thêm vợ/chồng lúc sửa, hoặc xoá người). Vẫn cần API vì logic đọc hợp nhất hai chiều.

### 4.6 Nối người đã có làm con (`linkChild`)

Input: `parentId`, `childId`, `otherParentId?`.

- Giới tính parent quyết định ô: `'female'` → mẹ, còn lại (kể cả `'unknown'`) → cha.
- Ô đích đã có người khác → `PARENT_SLOT_TAKEN`, **không đè**.
- Sau khi ghi ô thứ nhất, điền ô còn lại nếu:

  - Caller chỉ đúng `otherParentId` và người đó thuộc danh sách ứng viên, **hoặc**
  - Không chỉ và có **đúng 1** ứng viên.

Ứng viên ô còn lại = `getPartners(parent)` lọc giới tính hợp ô.

`getPartners` = vợ/chồng tường minh **cộng** người có con chung mà chưa nối hôn (`coParents`). Khi một người có đủ cha **và** mẹ (qua `set-parent`, `link-child`, `add-relative` father/mother, hay nối theo nhãn), server **tự ghi** cạnh vợ chồng `'married'` giữa hai người đó nếu chưa có — giống app từ schema v3 ("Đủ cha+mẹ → ghi vợ chồng"). Đổi cha/mẹ sau đó không tự gỡ. Nếu không ghi, nối người cha với một người vợ sau sẽ bị tính là "vợ/chồng đầu tiên" và tự điền vào ô mẹ còn trống của các con khác (§4.4). `coParents` chỉ còn gặp ở dữ liệu cũ.

### 4.7 Thêm người thân từ một người (`addRelative`)

Đây là đường chính dựng cây: bấm node → chọn vai → form → tạo + nối một nhịp.

Input: `anchorId`, `kind`, draft người mới, `spouseId?` (khi thêm con mà anchor có ≥ 2 vợ/chồng).

`kind`: `'father' | 'mother' | 'spouse' | 'child' | 'sibling'`

| kind | Việc làm | Chặn trước khi tạo |
|---|---|---|
| `father` | Tạo người, `setFather(anchor, mới)` | Ô cha đã có |
| `mother` | Tạo người, `setMother(anchor, mới)` | Ô mẹ đã có |
| `spouse` | Tạo người, `linkSpouse(anchor, mới)` | — |
| `child` | Tạo người, đặt anchor vào ô cha/mẹ theo giới tính, rồi `fillOtherParent` | — |
| `sibling` | Tạo người, copy `fatherId`/`motherId` của anchor | Anchor chưa có cha **và** chưa có mẹ. Không bịa cha mẹ ẩn. |

Tạo bản ghi **sau** khi kiểm chặn, nếu không đẻ ra người mồ côi.

### 4.8 Thêm người lẻ rồi tự nối theo nhãn

Form "Thêm người" (không `anchorId`): tạo Person, rồi nếu nhãn "Quan hệ với bạn" chỉ đúng **một cạnh** so với "tôi", ghi cạnh đó.

| Nhãn | Cạnh ghi | Điều kiện |
|---|---|---|
| Cha / Mẹ | `setFather/Mother(self, mới)` | Ô chưa có |
| Ông nội / Bà nội | đặt cha/mẹ của **cha tôi** | Đã có cha, ô ông/bà chưa có |
| Ông ngoại / Bà ngoại | đặt cha/mẹ của **mẹ tôi** | Đã có mẹ, ô ông/bà chưa có |
| Vợ / Chồng | `linkSpouse(self, mới)` | — |
| Con | `linkChild(self, mới)` | — |
| Anh / Chị / Em | copy cha+mẹ của tôi sang người mới | Đã có ≥ 1 cha hoặc mẹ |

Không tự nối: `Cụ / Tổ tiên`, `Cháu`, `Chắt`, `Hậu duệ`, nhãn tự nhập — mơ hồ (cụ nào, cháu của ai). App vẫn **lưu người**, không chặn; họ vào nhóm "chưa nối vào cây".

Vai chỉ có một (Cha, Mẹ, Ông/Bà nội/ngoại) mà "tôi" đã khai thì form **không mời lại**.

---

## 5. Dẫn xuất — API không cần lưu, client tự tính được

Nếu BE muốn trả sẵn cho UI, tính theo đúng công thức sau. Sai công thức là cây/màn chi tiết lệch nhau.

| Khái niệm | Công thức |
|---|---|
| Con | mọi person có `fatherId` hoặc `motherId` = X. Sort: `birthOrder` asc (thiếu = ∞) → `createdAt` → `id` |
| Anh chị em | con của cha hoặc mẹ của X, trừ X. `half` chỉ khi **cả hai** đã biết người cùng ô **và** hai người đó khác nhau. Mẹ chưa nhập ≠ mẹ khác |
| Ông bà nội | cha+mẹ của cha |
| Ông bà ngoại | cha+mẹ của mẹ |
| Cháu | con của các con (đúng 1 đời, không gồm chắt) |
| Partners (màn chi tiết "Vợ / chồng") | spouses tường minh + co-parents |
| Tổ tiên | leo `fatherId`/`motherId` |
| Gốc vẽ nhánh | từ một người, lặp `fatherId ?? motherId` cho tới hết |
| Cụm (component) | union-find theo cạnh cha–con **và** vợ–chồng. Hôn nhân nối hai họ thành một cụm |
| Người lẻ (unlinked) | cụm size = 1. **Không** vẽ thành cây 1 node |
| Đời tương đối | BFS: cha/mẹ −1, con +1, vợ/chồng 0. Không tới được = cụm khác |

Gốc mặc định khi mở màn cây:

1. Có `selfId` → tổ của self
2. Không → gốc cụm lớn nhất (cụm chứa self luôn đứng đầu)

Nhãn cụm: `"Nhà {tên người đời cao nhất}"`. Hoà đời thì ưu tiên nam → `createdAt` → `id`.

---

## 6. Ứng viên khi nối (để BE lọc hoặc để client lọc)

App lọc trên client. Nếu BE làm endpoint "candidates", khớp luật này:

**Cha / mẹ của person P** — người đời −1 so với P:

- Không phải P
- Giới tính không bị loại (ô cha ≠ female, ô mẹ ≠ male)
- `canSetParent` không lỗi
- Thuộc cùng cụm, **hoặc** là người lẻ hoàn toàn (chưa cha/mẹ/con/vợ chồng)
- Người cụm khác đã có vai vế **không** được mời (trộn hai gia phả)
- Nếu ô kia đã có người: ưu tiên bó theo partners của người đó (mẹ của con phải là vợ/co-parent của cha). Nhóm đó rỗng thì mới liệt kê rộng
- Người đang giữ ô luôn có trong list (để không mất giá trị hiện tại)

**Vợ/chồng của P** — cùng đời (0):

- Chưa nối với P
- Không phải anh chị em
- Không cùng giới tính khi **cả hai đã biết**
- Cùng cụm hoặc người lẻ

**Cha/mẹ còn lại khi thêm con** — chỉ `getPartners(anchor)` lọc giới tính, không phải cả danh bạ.

Người đang sửa **chưa nối ai** thì bỏ lọc đời (chưa có chỗ đứng để so). Đó là đường kéo người lẻ về cây.

---

## 7. Ngày giỗ (âm lịch)

Nguồn: `deceased && lunarDeathDay ∈ [1,30] && lunarDeathMonth ∈ [1,12]` (`hasLunarDeath`).

### 7.0 Xung đột nguồn âm lịch — **CẦN CHỐT**

- Backend (`giapha/services/vn_lunar.py`) dùng thuật toán **Hồ Ngọc Đức, múi giờ UTC+7** — lịch Việt Nam. Chọn có chủ đích ở plan `260905` (lịch Trung Quốc UTC+8 lệch ngày → giỗ sai). `solarDeathDate` (§2.4) và nhắc giỗ dòng họ đều tính bằng nó.
- App dùng bảng tra kiểu **TK** (`getLunarDate` / `getSolarDateSafe`). Các bảng TK phổ biến là lịch **Trung Quốc (UTC+8)**. Nếu đúng vậy thì hai bên **lệch**: 1900–2100 có 2.814 ngày khác nhau, 462 ngày khác cả tháng; Tết khác ở 10 năm (1965, 1968, 1969, **1985 lệch một tháng**, 2007, 2030, 2053…). Trong 2026–2040 các tháng lệch: 2030 tháng 1; 2031 tháng 3 nhuận; 2032 tháng 2; 2034 tháng 8; 2037 tháng 3; 2038 tháng 3; 2039 tháng 11 — giỗ rơi vào các tháng này sẽ nhắc khác ngày giữa app (Notifee) và server (FCM dòng họ).
- **Đề xuất:** lấy **Hồ Ngọc Đức UTC+7** làm nguồn sự thật cho cả hai. App kiểm bảng TK bằng bộ vector dưới; lệch thì thay bằng port của `vn_lunar` (bản JS trong `plans/visuals/gia-pha-prototype/js/lunar-calendar-gio-dates.js` khớp backend 400/400 ngày ngẫu nhiên 1950–2059).

| Dương lịch | Lịch VN (UTC+7) — đúng | Bảng UTC+8 cho ra |
|---|---|---|
| 21/01/1985 | mùng 1 tháng Giêng năm 1985 | mùng 1 tháng Chạp năm 1984 (lệch một tháng) |
| 17/02/2007 | mùng 1 tháng Giêng năm 2007 | 30 tháng Chạp năm 2006 |
| 02/02/2030 | mùng 1 tháng Giêng năm 2030 | 30 tháng Chạp năm 2029 |
| 19/09/2026 | mùng 9 tháng Tám năm 2026 | mùng 9 tháng Tám năm 2026 (trùng, vector đối chứng) |

Quy tắc lặp năm âm (`src/utils/lunar-recurrence.ts`) — nếu BE tính mốc nhắc:

1. Dùng **cùng một nguồn âm lịch** ở app và server (§7.0). Trộn hai họ thuật toán/bảng lệch tới **một tháng**.
2. Mốc ngày 30 mà tháng đó năm ấy chỉ có 29 ngày → **lùi 29**, không dồn mùng 1 tháng sau.
3. Tháng nhuận: giỗ cúng **tháng thường**. `lunarLeap` chỉ để hiển thị.
4. `deathTime` / giờ mất **không** tham gia tính giỗ.

Nhắc trên máy hiện do Notifee local. Nếu BE gửi push: lặp `repeatType = 5` phải dựa ngày âm, không cộng 365 ngày dương (~11 ngày lệch/năm).

---

## 8. Đề xuất API khớp thao tác app

Auth: user đã đăng nhập. Mọi resource thuộc **gia phả của user đó**. Không share / không multi-tree trong app hiện tại.

> §8 là đề xuất ban đầu; **bản đã triển khai** ở `docs/api-reference.md`. Đã chốt khác với đề xuất: prefix `/api/gia-pha`; `POST /persons` trả `linked` + `hint`; mọi mutation trả `{ok, person, persons, warning}`; xoá người **giữ** sự kiện giỗ (gioEventId đứt, app tra lại); giỗ chỉ qua `PUT .../gio-event` (không có `/v1/events`, §3.3).

### 8.1 Đọc

```
GET /v1/family
```

Trả cả cây + meta. Đủ cho màn cây, danh sách, chi tiết.

```json
{
  "selfId": "uuid | null",
  "persons": [ "Person..." ]
}
```

```
GET /v1/family/persons/{id}
```

Chi tiết một người. Client có thể tự dẫn xuất quan hệ từ `GET /v1/family`; endpoint này optional.

### 8.2 Tạo / sửa thông tin (không đụng quan hệ)

```
POST /v1/family/persons
PATCH /v1/family/persons/{id}
```

Body = `PersonDraft`: mọi field Person **trừ** `id`, `createdAt`, `updatedAt`, `fatherId`, `motherId`, `fatherRel`, `motherRel`, `spouses`.

Sửa thông tin **không** được phép đổi cạnh. App tách cố ý: quan hệ chỉ đi qua mutation dưới.

`POST` không `kind` = thêm người lẻ. Nếu body có `relationship` và đã có `selfId`, BE **có thể** tự nối theo bảng mục 4.8 (app đang làm lúc lưu). Nên làm server-side để hai client không lệch; trả `linked: true/false` + `hint` nếu chưa nối được.

Công tắc "Đây là tôi":

```
PUT /v1/family/self
{ "personId": "uuid | null" }
```

Chỉ cho set khi hiện `selfId == null` hoặc đang gỡ/đổi đúng người đang giữ. App không cho cướp vai từ người khác trên UI.

### 8.3 Mutation quan hệ (mỗi lệnh một endpoint)

Không nhận "cả graph" từ client. Mỗi thao tác UI = một call, server kiểm bất biến rồi ghi atomic.

```
POST /v1/family/relations/add-relative
{
  "anchorId": "uuid",
  "kind": "father" | "mother" | "spouse" | "child" | "sibling",
  "person": { /* PersonDraft */ },
  "otherParentId": "uuid | null"   // chỉ khi kind=child
}

POST /v1/family/relations/set-parent
{ "childId": "uuid", "slot": "father" | "mother", "parentId": "uuid | null", "rel": "blood" | "adopted" }

POST /v1/family/relations/link-spouse
{ "aId": "uuid", "bId": "uuid", "type": "married" | "divorced" }

POST /v1/family/relations/unlink-spouse
{ "aId": "uuid", "bId": "uuid" }

POST /v1/family/relations/link-child
{ "parentId": "uuid", "childId": "uuid", "otherParentId": "uuid | null" }
```

`set-parent` với `parentId: null` = `clearFather` / `clearMother`.

Response thống nhất:

```json
{
  "ok": true,
  "person": { },
  "persons": [ ],
  "warning": { "code": "SPOUSE_IS_ANCESTOR", "message": "..." }
}
```

Lỗi:

```json
{
  "ok": false,
  "error": {
    "code": "PARENT_CYCLE",
    "personId": "...",
    "otherId": "...",
    "message": "Không đặt được: người này đang là con cháu trong nhánh đó, nối vào sẽ tạo vòng lặp."
  }
}
```

`message` nên là câu tiếng Việt app đang dùng (copy từ `family-graph.ts` / `family-relations.ts`) để UI hiện nguyên.

Sau mutation, trả **cả `persons[]` mới** (cây nhỏ). Client hiện đọc lại toàn bộ list sau mỗi lần focus.

### 8.4 Xoá

```
DELETE /v1/family/persons/{id}
```

Response:

```json
{
  "deleted": true,
  "detachedFrom": ["uuid..."],
  "selfId": "uuid | null"
}
```

Không cascade. Không xoá sự kiện giỗ kèm theo (app hiện cũng không xoá event khi xoá người — `gioEventId` đứt, sự kiện vẫn trong tab Sự kiện). Nên thống nhất: **giữ event** hoặc **xoá event** — chốt một và ghi rõ; app hiện = giữ event mồ côi.

### 8.5 Giỗ

Nếu sự kiện cũng lên server:

```
POST /v1/events
PATCH /v1/events/{id}
DELETE /v1/events/{id}
```

Khi tạo từ gia phả, body thêm `linkPersonId`. Server ghi `Person.gioEventId`.

Hoặc gói trong family:

```
PUT /v1/family/persons/{id}/gio-event
{ "eventId": "uuid" }
```

Xoá event: `gioEventId` có thể để nguyên (app tra lại, coi như chưa đặt). Endpoint chi tiết người phải **join event**; đừng tin mỗi id.

---

## 9. Luồng UI ↔ API (để test)

```
Gia phả trống
  → POST /persons + PUT /self { personId }   (không có field isSelf; "tôi" là scalar, §2.2)
  → cây 1 người, chưa vẽ (size=1 = unlinked cho tới khi có quan hệ)

Bấm node → Thêm cha
  → POST /relations/add-relative { kind: "father", ... }
  → gender mặc định male; relationship gợi ý "Cha" nếu anchor là self

Thêm mẹ cho cùng người
  → add-relative kind=mother
  → server tự ghi cạnh vợ chồng 'married' giữa cha và mẹ (đủ cha+mẹ → vợ chồng)

Thêm con khi đã có 2 vợ
  → add-relative kind=child + otherParentId bắt buộc chọn trên form

Sửa người → đổi ô Cha thành "Chưa rõ"
  → set-parent { slot: "father", parentId: null }

Sửa người → thêm vợ/chồng từ danh sách
  → link-spouse (không gỡ người cũ)

Xoá người giữa nhánh
  → DELETE; con cháu còn; cạnh đứt; có thể thành 2 cụm + người lẻ
```

Chỉ tên là bắt buộc lúc lưu. Mọi field khác optional. "Lưu và thêm tiếp" chỉ với `child` và `sibling` (cha/mẹ thì người thứ hai bị từ chối).

---

## 10. Việc BE **không** cần làm

| Việc | Lý do |
|---|---|
| Layout cây, toạ độ node, pinch/zoom | Client (`relatives-tree`) |
| Ô trống / ghost-spouse lúc vẽ | Client, không persist |
| Tính "còn N ngày tới giỗ" trên list cây | Client; BE chỉ cần lưu mốc âm |
| Migration `local_memorials` (Giỗ cũ) | Chỉ chạy 1 lần trên máy, schema v2 |
| `family_lineage_of_id` | State xem UI |
| Suy nhãn bác/chú/cô/dì theo vùng | App cố ý không suy; user nhập |

---

## 11. Gợi ý triển khai DB

Bảng tối thiểu:

```
families
  id, user_id UNIQUE, self_person_id NULLABLE, created_at, updated_at

family_persons
  id, family_id,
  name, gender, deceased,
  father_id NULLABLE, mother_id NULLABLE,
  father_rel NULLABLE, mother_rel NULLABLE,
  solar_birth_date, birth_time, birth_order,
  solar_death_date, death_time,
  lunar_death_day, lunar_death_month, lunar_death_year, lunar_leap,
  relationship, note, phone, education, occupation, gio_event_id,
  created_at, updated_at

family_spouses
  family_id, person_a_id, person_b_id, type
  UNIQUE (family_id, least(a,b), greatest(a,b))
```

Không bảng `children` / `siblings`.

Constraint gợi ý:

- `father_id` / `mother_id` FK cùng `family_id`, `ON DELETE SET NULL` (khớp "xoá không lan")
- Check `father_id != id`, `mother_id != id`
- Check chu trình **trong application** (SQL recursive CTE lúc ghi `set-parent`)
- Unique `(family_id)` trên `families.user_id`
- `self_person_id` FK, `ON DELETE SET NULL`

Transaction: `linkSpouse` + điền ô cha/mẹ trống của con = **một** transaction.

---

## 12. Nhập gia phả từ máy lên server — [Planned · phase 3]

1. User mới / máy trống → CRUD thẳng server.
2. Máy đã có `Person[]` (schema v2, sau migration Giỗ) → **một lần** `PUT /api/gia-pha/v1/family/import`.
3. Id `gio_*` là di sản từ tính năng Giỗ cũ; giữ nguyên, đừng regenerate — từng gắn notification local.

```
PUT /v1/family/import
{ "importKey": "uuid app sinh 1 lần/máy", "selfId": "fam_…|null", "persons": [ Person… (id client, đủ cạnh) ] }
→ 200 { "idMap": { "fam_…": "uuid" }, "selfId": "uuid|null", "persons": [ … ],
        "skippedEdges": [ { "code", "personId", "otherId", "message" } ],
        "warnings": [ { "personId", "field", "message" } ] }
```

| Luật | Chi tiết |
|---|---|
| Chỉ khi server trống | Đã có người và `importKey` khác → **409 `FAMILY_NOT_EMPTY`**. Không ghi đè, không gộp |
| Idempotent | Cùng `importKey` gửi lại → 200, trả đúng `idMap` cũ (server lưu `Family.import_key`, `FamilyPerson.legacy_id`) |
| Người luôn vào | Cạnh lỗi bị **bỏ** và báo trong `skippedEdges`: `DANGLING_*`, `SELF_PARENT`, `PARENT_CYCLE`, `GENDER_MISMATCH`, `SELF_SPOUSE`. `SPOUSE_IS_ANCESTOR` vẫn giữ |
| Tất định | Xét cạnh theo `createdAt` → `id` |
| Field xấu | Tên trống → "Chưa đặt tên"; quá dài → cắt (`name` 60, `relationship` 24, `note` 500, `phone` 20, `education`/`occupation` 40, `gioEventId` 64); ngày/giờ sai → null; kèm `warnings` |
| Giữ nguyên | `gioEventId`, `createdAt`, `updatedAt` từ client |
| Giới hạn | `FAMILY_MAX_PERSONS` = 1000 người (vượt → 400); throttle 5 lần/giờ/user |

App: dùng `idMap` đổi id local (`fatherId`/`motherId`/`spouses`/`selfId`), giữ MMKV làm dự phòng tới khi đổi xong, rồi chuyển hẳn sang API.

Nhiều thiết bị: sau import, server là nguồn sự thật. Gia phả cá nhân **không** có khoá phiên bản → last-write-wins theo request tới sau. Chấp nhận ở v1 (một người sửa cây của chính mình). Dòng họ có `version` (§14.5).

---

## 13. Checklist nghiệm thu API vs app

- [ ] Tạo người chỉ cần `name`; `gender` default `'unknown'`; `deceased` default `false`; `spouses` = `[]`
- [ ] PATCH person không đổi được `fatherId` / `spouses`
- [ ] `selfId` tối đa 1; xóa người đang là self → `selfId` null
- [ ] Thêm cha lần 2 trên cùng người → lỗi, không tạo bản ghi mồ côi
- [ ] Thêm anh chị em khi chưa có cha mẹ → lỗi
- [ ] `linkSpouse` ghi 2 chiều; gỡ 1 chiều rồi `GET` không tự nối lại
- [ ] Cưới vợ đầu tiên khi đã có con thiếu mẹ → tự điền `motherId` nếu giới tính hợp
- [ ] Cưới vợ hai **không** tự gán con của vợ cả
- [ ] Nối con vào ô đã có cha khác → `PARENT_SLOT_TAKEN`
- [ ] Đặt cháu làm cha ông → `PARENT_CYCLE`
- [ ] Xoá ông → cháu còn, `fatherId` của con ông thành null
- [ ] `deceased: true` không bắt buộc ngày mất
- [ ] Có ngày+tháng âm, thiếu năm → vẫn coi là có mốc giỗ
- [ ] `lunarDeathDay` 0 hoặc 13 → không phải mốc giỗ hợp lệ
- [ ] Ngày dương lưu `DD-MM-YYYY`, giờ `HH:mm` tách field
- [ ] `relationship` là string, không phải enum int
- [ ] Response lỗi có `code` + `message` vi
- [ ] Không endpoint nào bắt client gửi `children[]`
- [ ] App và server cho **cùng** ngày âm với bộ vector §7.0
- [ ] Import: server trống → 200 + `idMap`; gửi lại cùng `importKey` → cùng `idMap`; server có dữ liệu → 409 (§12)
- [ ] Import: snapshot có vòng cha–con → mọi người vào, đúng một cạnh trong `skippedEdges` (§12)
- [ ] Người đã liên kết: `GET /v1/family` trả tên/ngày từ dòng họ; sửa ở họ → thấy ngay, không job đồng bộ (§14)
- [ ] Sửa field chung của người đã liên kết ngoài phạm vi → `clanWrites[].result = "proposed"`, field riêng vẫn lưu (§14.5)
- [ ] Gợi ý ghép không bao giờ tự tạo liên kết; ghép chỉ theo tên thì phải trùng năm sinh (§14.3)
- [ ] Rời họ → liên kết tự tách, cây cá nhân giữ giá trị cuối, đề xuất chờ → `withdrawn`; owner rời → 400 (§14.4)
- [ ] `phone`/`education`/`occupation`/`note` của người đã liên kết chỉ lưu ở cá nhân, không vào `clanWrites` (§14.5)

---

## 14. Liên kết gia phả cá nhân ↔ dòng họ — [Planned · phase 4–5]

Nguồn quyết định: `plans/reports/brainstorm-260919-shared-clan-tree-collaboration.md`. Mockup: `plans/visuals/gia-pha-app-mockup.html`; bản dùng thử: `plans/visuals/gia-pha-prototype/`.

### 14.1 Nguyên tắc: tham chiếu, không đồng bộ

Một người thuộc nhiều họ (nội, ngoại, nhà vợ) → giữ **hai loại cây**: gia phả cá nhân (riêng, xuyên họ) và dòng họ (`/clans`, dùng chung). Một người trong cây cá nhân **liên kết** tới tối đa một người **mỗi họ**:

```
FamilyPersonLink(family, family_person, clan, clan_person, linked_by, created_at)
UNIQUE (family_person, clan), UNIQUE (family, clan_person)
```

Người đã liên kết **đọc field chung thẳng từ dòng họ** lúc `GET` — mỗi field một nguồn, không copy, không job đồng bộ. Cấu trúc (cha/mẹ/vợ chồng) mỗi cây **giữ riêng**; lệch thì chỉ báo (§14.4), không tự sửa.

### 14.2 Field chung và riêng

| Person (cá nhân) | Clan `Person` | Loại |
|---|---|---|
| `name` | `ho_ten` | chung |
| `gender` `male/female/unknown` | `gioi_tinh` `nam/nu/khac` | chung |
| `deceased` | `da_mat` (**thêm mới**, data migration từ dấu mất hiện có) | chung |
| `solarBirthDate` `DD-MM-YYYY` | `birth_solar` (Date) | chung |
| `lunarDeathDay/Month`, `lunarLeap` | `death_lunar_day/month`, `death_lunar_leap` | chung |
| `lunarDeathYear`, `solarDeathDate` | suy từ `death_solar` qua `vn_lunar` | chung |
| `birthTime`, `deathTime`, `relationship`, `note`, `phone`, `education`, `occupation`, `gioEventId`, `birthOrder` | — | **riêng** |
| — | ảnh, tên huý/tự/hiệu, mộ phần, tiểu sử, đời, chi | chỉ ở họ |

Ánh xạ nằm ở **một** module (`giapha/services/family_clan_field_map.py`), test round-trip mọi field.

### 14.3 Endpoint

| Method | Path | Việc |
|---|---|---|
| `GET` | `/v1/family` | Thêm `links: [{id, personId, clanId, clanPersonId, clanName}]`; người đã liên kết trả field chung đã ghép + `linked: true`. **Không có** `GET /v1/family/links` — đây là nguồn duy nhất của danh sách liên kết |
| `POST` | `/v1/family/clans` | `{rootPersonId, tenHo, thuyTo?}` — chép gốc + hậu duệ + vợ/chồng hậu duệ thành họ mới, liên kết tất cả, caller = owner, binding = bản chép của `selfId` (đã xác minh). Atomic |
| `GET` | `/v1/family/links/suggestions?clanId=` | Cặp gợi ý `{personId, clanPersonId, confidence: high/low, reason}` |
| `POST` | `/v1/family/links` | `{clanId, pairs:[{personId, clanPersonId}]}` — user xác nhận, tối đa 200 |
| `DELETE` | `/v1/family/links/{id}` | **Tách**: chép field chung hiện tại của họ về cá nhân rồi xoá liên kết |
| `POST` | `/v1/family/links/import` | `{clanId, clanPersonIds[]}` — "Nhận về": tạo người cá nhân + liên kết; nối cạnh với người đã liên kết theo luật §4, lỗi → `skippedEdges` |
| `POST` | `/v1/family/links/contribute` | `{personId, clanId}` — "Đóng góp": trong phạm vi (§15) → tạo thẳng ở họ + liên kết; ngoài → đề xuất `create_person`, duyệt xong tự liên kết |
| `GET` | `/v1/family/links/diff?clanId=` | Cặp đã liên kết có cha/mẹ/vợ chồng lệch |

**Ghép gợi ý:** (1) neo cặp `selfId` ↔ binding của user trong họ; (2) lan theo cha, mẹ, vợ/chồng, con khớp tên chuẩn hoá → `high`; (3) còn lại: tên bỏ dấu **và trùng năm sinh** (hai bên đều có năm) → `low`, mặc định không chọn. **Không bao giờ tự liên kết.** Gia phả cá nhân chưa lên server → gợi ý import (§12) trước.

### 14.4 Vòng đời liên kết

- Rời họ (`DELETE /clans/{id}/members/me`) / bị xoá khỏi họ / họ xoá mềm / người trong họ xoá mềm → **tự tách** cho user đó (chép snapshot trước). Rời họ còn chuyển mọi đề xuất `pending` của người đó trong họ sang `withdrawn`. Owner không tự rời được (400) — phải chuyển quyền trước.
- Xoá người trong cây cá nhân → chỉ xoá bên cá nhân; người trong họ giữ nguyên.
- Hard-delete người trong họ (chỉ qua admin) → liên kết cascade; cá nhân rơi về giá trị lưu cũ.
- Diff chỉ báo ("Họ ghi vợ của Dũng là …; cây của bạn chưa có"); user tự sửa.

### 14.5 Sửa người đã liên kết (phase 5)

`PATCH /v1/family/persons/{id}` với người đã liên kết:

- Field **riêng** (kể cả `phone`/`education`/`occupation`/`note`) → lưu ở cá nhân ngay; không bao giờ vào `clanWrites` hay payload đề xuất.
- Field **chung** → với **từng** họ đã liên kết: có quyền (§15) thì ghi thẳng họ, kiểm `version`; không có quyền thì tạo đề xuất `update_person`.
- Body thêm `clanVersions: {clanId: n}` (chỉ `PATCH` đọc; `POST /v1/family/persons` bỏ qua). Response **luôn HTTP 200**, thêm `clanWrites: [...]`, mỗi họ một phần tử: `{clanId, result: "applied", version}` \| `{clanId, result: "proposed", changeRequestId}` \| `{clanId, result: "conflict", current}` (`current` = **toàn bộ** người trong họ, shape `GET /clans/{id}/persons/{pid}`) \| `{clanId, result: "rejected", errors | message}`. `[]` khi không đổi field chung nào. Một họ lỗi không chặn phần riêng hay họ khác.
- Clan `Person.version` tăng ở **mọi** đường ghi. `PATCH /clans/{id}/persons/{pid}` nhận `version`; lệch → **409 `VERSION_CONFLICT`** kèm giá trị mới nhất. Không gửi `version` → không kiểm (client cũ).
- Mutation quan hệ cá nhân (`add-relative`, `set-parent`, …) **không** lan sang họ. `add-relative` nhận thêm `contributeTo: [clanId]` để đóng góp ngay sau khi tạo; response thêm `contributions: [{clanId, result: "applied", clanPersonId} | {clanId, result: "proposed", changeRequestId} | {clanId, result: "error", error: {code, personId, otherId, message}}]` (người mới trong cây cá nhân đã lưu, không rollback).

---

## 15. Quyền trong dòng họ (phần app phải phản ánh) — [Planned · phase 1, 2, 6]

API dòng họ `/clans/*` ở `docs/api-reference.md`; mục này gom phần app cần để hiển thị đúng.

| Vai trò | Sửa trực tiếp | Duyệt |
|---|---|---|
| `owner` — Trưởng họ | Toàn họ | Mọi thứ; gán vai trò; lời mời Biên tập viên |
| `manager` — Ban quản lý (**mới**) | Toàn họ | Lời mời thành viên, xác minh, đề xuất (thay trưởng họ). Không đổi vai trò, không đụng cài đặt họ |
| `editor` — Biên tập (toàn họ) | Toàn họ | Đề xuất. **Không** xác minh |
| `editor` + `scope_root_person` — Trưởng chi | Nhánh con cháu của gốc | Đề xuất và xác minh trong chi |
| `viewer` đã xác minh — Thành viên | **Phạm vi gia đình** | — |
| `viewer` chưa xác minh | Không (chỉ gửi đề xuất) | — |

- **Phạm vi gia đình** của người P: P, vợ/chồng, cha mẹ, con cháu + vợ/chồng của con cháu, và anh chị em ruột **chưa được ai xác minh nhận**.
- **Xác minh "tôi là ai"**: nhận qua lời mời gắn người → xác minh ngay; tự nhận → chờ owner / manager / trưởng chi của chi đó. Chưa xác minh vẫn nhận nhắc giỗ.
- **UI dựa vào server, không tự tính quyền**: `GET /clans/{id}/persons/{pid}` trả `can_edit: "direct" | "propose"`; `GET /clans/{id}/tree` trả `my_editable_ids` (null = toàn họ) để vẽ viền "gia đình bạn". `PATCH` ngoài phạm vi → 403 kèm gợi ý; app gọi `POST /clans/{id}/change-requests` thay.
- **Đề xuất** (`ChangeRequest`): body tạo `{action, target_person_id?, target_marriage_id?, payload: {...}, note?}` (`note` lưu thành `proposer_note`); kiểm hợp lệ ngay lúc gửi; người duyệt = owner/manager/editor **có quyền ghi mọi người đề xuất đụng tới** (trưởng chi chỉ trong chi); nhắc người duyệt ngày 7, **hết hạn ngày 30**; duyệt khi người đó đã bị sửa sau đó → 409 `stale` trừ khi `override_stale`. Người gửi rời họ → đề xuất `pending` thành `withdrawn`.
- **Mời**: owner, manager, editor và thành viên đã xác minh tạo được. Người trong phạm vi + quyền thành viên → `active`, có mã ngay; ngoài phạm vi / không gắn người → `pending_approval` (owner hoặc manager duyệt); quyền biên tập viên → chỉ owner duyệt. Lời mời chờ duyệt **chưa có mã**.
