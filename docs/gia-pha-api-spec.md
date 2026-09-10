# Gia phả — hợp đồng dữ liệu cho Backend

Tài liệu cho BE thiết kế API **khớp đúng logic app hiện tại**. Nguồn sự thật là code, không phải mô hình giả định:

- Kiểu: `src/types/family.ts`, `src/types/event.ts`
- Ghi dữ liệu: `src/services/family-storage.ts`, `src/services/family-relations.ts`
- Luật đồ thị: `src/utils/family-graph.ts`, `src/screens/FamilyScreen/relative-link-rules.ts`
- Form / chi tiết: `src/screens/FamilyScreen/FamilyPersonFormScreen.tsx`, `FamilyPersonDetailScreen.tsx`

Kiến trúc vẽ cây (layout, pinch/zoom) **không** thuộc phạm vi API — xem `docs/gia-pha-architecture.md`.

---

## 1. Trạng thái hiện tại

Gia phả **chưa có API**. Toàn bộ nằm local MMKV trên máy:

| Key | Nội dung |
|---|---|
| `family_persons` | JSON `Person[]` — nguồn sự thật |
| `family_self_id` | id người được đánh dấu "tôi" |
| `family_lineage_of_id` | id người đang xem theo dòng họ (UI, không bắt buộc sync) |
| `local_events` | JSON sự kiện (gồm nhắc giỗ) |

Không gắn với tài khoản đăng nhập. Xoá tài khoản Firebase **không** xoá gia phả trên máy (đang ghi trong chính sách quyền riêng tư). Khi đưa lên server: **một user = một gia phả**, và cần cập nhật chính sách quyền riêng tư vì dữ liệu hiện được cam kết "không rời khỏi máy".

Quy mô thực tế: người dùng tự nhập, **< 500 người**. Không cần phân trang phức tạp; `GET` cả cây là đủ.

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
  lunarDeathYear?: number | null; // có thể thiếu
  lunarLeap?: boolean | null;     // tháng nhuận; giỗ vẫn cúng tháng thường

  relationship?: string | null;   // nhãn với "tôi", max 24, lưu CHỮ không phải enum id
  note?: string | null;           // max 200
  gioEventId?: string | null;     // id sự kiện nhắc giỗ, nếu đã tạo

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

`getPartners` = vợ/chồng tường minh **cộng** người có con chung mà chưa nối hôn (`coParents`). Cặp dựng bằng "Thêm Cha" rồi "Thêm Mẹ" **không** có cạnh vợ chồng — họ là đồng-phụ-huynh, không tự ghi `'married'` (có con chung ≠ đã cưới).

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

Quy tắc lặp năm âm (`src/utils/lunar-recurrence.ts`) — nếu BE tính mốc nhắc:

1. Dùng **cùng bảng tra lịch** với app (cặp `getLunarDate` / `getSolarDateSafe` kiểu TK). Trộn với công thức thiên văn/`date-chinese` lệch tới **một tháng**.
2. Mốc ngày 30 mà tháng đó năm ấy chỉ có 29 ngày → **lùi 29**, không dồn mùng 1 tháng sau.
3. Tháng nhuận: giỗ cúng **tháng thường**. `lunarLeap` chỉ để hiển thị.
4. `deathTime` / giờ mất **không** tham gia tính giỗ.

Nhắc trên máy hiện do Notifee local. Nếu BE gửi push: lặp `repeatType = 5` phải dựa ngày âm, không cộng 365 ngày dương (~11 ngày lệch/năm).

---

## 8. Đề xuất API khớp thao tác app

Auth: user đã đăng nhập. Mọi resource thuộc **gia phả của user đó**. Không share / không multi-tree trong app hiện tại.

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
  → POST /persons (isSelf=true) + PUT /self
  → cây 1 người, chưa vẽ (size=1 = unlinked cho tới khi có quan hệ)

Bấm node → Thêm cha
  → POST /relations/add-relative { kind: "father", ... }
  → gender mặc định male; relationship gợi ý "Cha" nếu anchor là self

Thêm mẹ cho cùng người
  → add-relative kind=mother
  → hai cha mẹ CHƯA có cạnh vợ chồng; partners = co-parents
  → cây vẫn vẽ thành cặp (client thêm "ghost spouse" / co-parent lúc layout)

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
  relationship, note, gio_event_id,
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

## 12. Đồng bộ / id cũ trên máy

App đang có dữ liệu local. Khi bật API cần chốt (ngoài phạm vi spec này nhưng BE nên biết):

1. User mới / máy trống → CRUD thẳng server.
2. Máy đã có `Person[]` → một lần `PUT /v1/family/import` nhận full snapshot, server cấp id mới, app remap `fatherId`/`motherId`/`spouses`/`selfId`/`gioEventId`.
3. Id `gio_*` là di sản từ tính năng Giỗ cũ; giữ nguyên nếu import, đừng regenerate — từng gắn notification local.

Conflict nhiều thiết bị: app hiện single-device. v1 có thể last-write-wins theo `updatedAt` trên từng person, hoặc "một device active".

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
