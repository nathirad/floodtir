# Floodtir — แผนที่ระบายน้ำและน้ำท่วม กทม.

แผนที่เชิงวิเคราะห์แบบ interactive สำหรับระบบระบายน้ำ กทม. รวมข้อมูลระดับน้ำในคลองแบบ near real-time จากสำนักการระบายน้ำ (สรน.)

---

## เปิดใช้งาน

เปิดไฟล์นี้ใน browser ได้เลย:

```
flood_bkk_map.html
```

> ไม่ต้องติดตั้งอะไร ไม่ต้อง server — ดับเบิลคลิกเปิดได้ทันที

---

## แผนที่มีอะไรบ้าง

| Layer | รายละเอียด |
|-------|-----------|
| **คลอง** | เครือข่ายคลองทั้ง กทม. ~2,000 เส้น ย้อมสีตามลำดับชั้น / สถานะระดับน้ำ / ความจุ |
| **แม่น้ำสายหลัก** | แม่น้ำเจ้าพระยาและสาขา |
| **สถานีวัดระดับน้ำ** | 301 สถานี อัปเดตทุก 5 นาที แสดงระดับน้ำ/เกณฑ์เตือนภัย |
| **อุโมงค์ระบายน้ำ** | อุโมงค์ใต้ดินขนาดใหญ่ |
| **ประตูระบายน้ำ** | floodgates ทั่ว กทม. |
| **สถานีสูบน้ำ** | pump stations |
| **บ่อสูบน้ำ** | sumps |
| **ท่อระบายน้ำ** | ดึง live จาก server กทม. เมื่อ zoom level ≥ 15 |
| **จุดเสี่ยงน้ำท่วม 473** | จุดเสี่ยงที่ กทม. ติดตาม |
| **น้ำท่วมถนน** | สถานีวัดระดับน้ำบนถนน |

### การคลิกบนแผนที่

- **คลิกที่คลอง** — แสดง popup ระดับน้ำเฉลี่ยในคลองนั้น, risk score, สถานะ normal/warning/critical
- **คลิกที่จุดสถานีวัดน้ำ** — แสดงข้อมูลเต็ม: ระดับน้ำปัจจุบัน, เกณฑ์เตือนภัย, เวลาอัปเดต
- **คลิกที่พื้นที่เขต (ว่างๆ)** — แสดง popup บอกชื่อเขต, รหัสเขต, และพื้นที่ตารางกิโลเมตร (ต้องเปิดเลเยอร์เขตก่อนนะ)
- **คลิกที่ layer อื่นๆ** — แสดงข้อมูล popup ของ feature นั้น

### โหมดสีคลอง

เปิด layer "คลอง" แล้วเลือกโหมดได้ที่แถบด้านซ้าย:
- **Hierarchy** — สีตามลำดับชั้น (คลองหลัก/คลองรอง)
- **Status** — สีตามสถานะระดับน้ำ (เขียว = ปกติ, เหลือง = เฝ้าระวัง, แดง = วิกฤต)
- **Capacity** — สีตามความจุที่เหลือ

---

## โครงสร้างไฟล์

```
Floodtirdatta/
│
├── flood_bkk_map.html        ← เปิดแผนที่วิเคราะห์น้ำท่วม กทม. ใน browser
├── river_dashboard.html      ← dashboard ระดับน้ำแม่น้ำเจ้าพระยาและสาขา
├── canal_graph.html          ← กราฟแสดงทิศทางการไหลของน้ำในคลอง (DAG)
├── update.bat                ← ไฟล์สคริปต์อัปเดตข้อมูลระดับน้ำ (รันอัตโนมัติ/ด้วยมือ)
│
├── templates/                ← โครงแบบ (Templates) สำหรับใช้ build แผนที่หลัก
├── scripts/                  ← สคริปต์ Python และตัววิเคราะห์ข้อมูลทั้งหมด
│
├── water-data/               ← ข้อมูลดิบและผลลัพธ์ระดับน้ำจากสรน. (อัปเดตทุก 5 นาที)
│   ├── water_latest_snapshot.json    ← ข้อมูลระดับน้ำล่าสุด
│   ├── water_edges_geojson.json      ← โครงข่ายเส้นเชื่อมสถานีวัดน้ำ (126 edges)
│   └── station_histories/            ← ข้อมูลสถิติประวัติระดับน้ำย้อนหลัง 273 ไฟล์
│
├── data/                     ← แหล่งเก็บข้อมูลดิบและผลลัพธ์เชิงวิเคราะห์ (หัวใจหลักของข้อมูล)
│   ├── geojson/              ← ไฟล์แผนที่ภูมิศาสตร์ (.geojson) ของ กทม.
│   │   ├── canals.geojson        ← เส้นคลองทั้งหมดในกรุงเทพฯ (~2,000 เส้น)
│   │   ├── districts.geojson     ← ขอบเขตเขตปกครองทั้ง 50 เขต
│   │   └── canals_chunks/        ← คลองที่หั่นย่อยแยกตามเขต (เพื่อโหลดแบบขี้เกียจ/Lazy load)
│   │
│   └── responsibility/       ← คลังข้อมูลอำนาจหน้าที่และความรับผิดชอบ (Responsibility Hash Index)
│       ├── inputs/               ← ข้อมูลนำเข้า เช่น ทะเบียนและหลักฐานข้อมูลดิบ
│       ├── candidate/            ← ข้อมูลการแนะนำผู้รับผิดชอบเชิงปฏิบัติการ (ยังไม่ยืนยัน)
│       ├── legal_authority/      ← ข้อมูลทางกฎหมายอ้างอิงและ พ.ร.บ. ของจริงพร้อม PDF
│       ├── evidence/             ← หลักฐานภารกิจและขั้นตอนการปฏิบัติงาน (SOP)
│       ├── normalized/           ← ข้อมูลที่ถูกจัดแจงโครงสร้างแล้ว พร้อมใช้วิเคราะห์ต่อ
│       ├── review/               ← รายการรอเจ้าหน้าที่หรือนิติกรตรวจและแก้ไขจุดขัดแย้ง
│       └── verified/             ← รายการยืนยันและอนุมัติสั่งการอย่างเป็นทางการ (Verified)
│
└── docs/                     ← เอกสารเชิงลึกและการวิเคราะห์
    ├── ANALYSIS.md           ← สรุป API, cadence และ pipeline
    ├── SCHEMA.md             ← โครงสร้าง schema และสัญญากับข้อมูล (Data Contract)
    ├── LEGAL_AUTHORITY_EVIDENCE.md  ← ข้อมูลทางกฎหมายและขอบเขตอำนาจ (PR #2)
    └── PR1_PR2_DATASETS_AND_SOURCES.md  ← สรุปงานและขอบเขต Dataset ทั้งหมดของ PR #1 และ PR #2
```

---

## 📂 สารบัญและการใช้ชุดข้อมูลทั้งหมด (Data Directory & Datasets Reference)

สำหรับผู้ที่จะนำชุดข้อมูลของ **Floodtir** ไปพัฒนาหรือใช้งานต่อ นี่คือคำอธิบายโฟลเดอร์ข้อมูลและไฟล์ย่อยที่จำเป็นทั้งหมด:

### 1. ข้อมูลระดับน้ำและโครงข่ายระบายน้ำ (Water & Telemetry Data)
เก็บอยู่ในโฟลเดอร์ `water-data/` และ `data/geojson/`
* **ข้อมูลสถานีและระดับน้ำล่าสุด (`water-data/water_all_stations.json` และ `water_latest_geojson.json`):**
  * มีข้อมูลสถานีตรวจวัดทั้งหมด **283 จุด** ครอบคลุมทั้ง กทม. และรอยต่อปริมณฑล
  * มีฟิลด์ `is_bangkok_area` ในการกรอง และพิกัดพร้อมค่าระดับน้ำเกณฑ์เตือนภัย (`warning_threshold` / `critical_threshold`)
* **เส้นคลอง กทม. (`data/geojson/canals.geojson`):**
  * มีเส้นแบ่งคลองรวม **1,951 เส้น** ย่อยข้อมูลสีตามระดับความจุ ความลึก และลำดับความสำคัญของคลอง
* **โครงข่ายสถานีเชื่อมต่อ (`water-data/water_edges_geojson.json`):**
  * โครงสร้างเส้นเชื่อมระดับน้ำ (126 เส้น) เพื่อวิเคราะห์ทิศทางและทำนายระดับน้ำในพื้นที่ที่ไม่มีสถานีวัดโดยตรง

### 2. ข้อมูลอำนาจหน้าที่และความรับผิดชอบ (Responsibility Hash Index - `data/responsibility/`)

ชุดข้อมูลนี้ถูกออกแบบมาเพื่อวิเคราะห์หา **"หน่วยงานใดต้องดูแลจุดน้ำท่วมนี้ตามพื้นที่และอำนาจกฎหมาย"** โดยแบ่งเป็นโฟลเดอร์ย่อยตามระดับสถานะความน่าเชื่อถือ:

| โฟลเดอร์ย่อย | ไฟล์สำคัญ | คำอธิบายและวิธีการนำไปใช้ |
|---|---|---|
| **`inputs/`** | `official_document_evidence.json` | ไฟล์รวบรวมหลักฐานและข้อมูลดิบก่อนนำไปสกัดเป็นมาตรากฎหมาย |
| **`candidate/`** | `agency_master.json`<br>`all_assignments.jsonl`<br>`geographic_jurisdiction_hash_index.jsonl` | **ข้อมูลแนะนำหน่วยงานปฏิบัติงาน:**<br>• ประกอบด้วยหน่วยงานหลัก 70 หน่วยงานแยกตามโครงสร้าง กทม.<br>• ผูก GeoHash7 (~150 เมตร) เข้ากับเขตและผู้ดูแลพื้นที่เพื่อใช้หาพิกัดแล้วยิงแนะนำผู้รับผิดชอบได้ทันทีในระดับ $O(1)$ |
| **`legal_authority/`** | `source_material.json`<br>`authority_provisions_hash_index.jsonl`<br>`district_authority_candidates.jsonl`<br>`dispatch_guardrails.json`<br>`legal_review_queue.jsonl` | **ข้อมูลทางกฎหมายและควบคุมสิทธิ์ (พ.ร.บ.):**<br>• สกัดกฎหมายจาก พ.ร.บ.หลัก 2 ฉบับ รวมเป็น 15 มาตรา เพื่อระบุว่าใครทำอะไรได้บ้าง (`action_codes`) ในเขตไหนบ้าง<br>• เก็บประวัติ PDF กฎหมายตัวจริงในโฟลเดอร์ย่อย `raw/`<br>• ตารางนโยบาย `dispatch_guardrails` ใช้สำหรับบล็อกห้ามระบบสั่งการอัติโนมัติแบบไม่มีคำสั่งเฉพาะเจาะจง |
| **`evidence/`** | `mission_duty_evidence_hash_index.jsonl`<br>`sop_process_evidence_hash_index.jsonl` | **ขั้นตอน SOP และภารกิจ:**<br>• รวมกระบวนการทำงานป้องกันน้ำท่วมของเขตและสำนักระบายน้ำเพื่อใช้อ้างอิงเวลาเกิดเหตุ |
| **`normalized/`** | `dim_source.csv`<br>`fact_district_agency_responsibility.csv`<br>`fact_data_quality_issue.csv` | **ตารางพร้อมใช้วิเคราะห์ (Normalized Data):**<br>• ข้อมูลทำมิติและตาราง Fact เรียบร้อยแล้ว เหมาะสำหรับยิงลงฐานข้อมูลเชิงวิเคราะห์ (BI / Analytics) |
| **`review/`** | `unresolved_asset_owners.jsonl`<br>`spatial_conflicts.jsonl` | **ข้อมูลรอความชัดเจน:**<br>• ทรัพย์สินที่ระบุเจ้าของไม่ได้ หรือเขตพื้นที่ที่มีความทับซ้อนทางภูมิศาสตร์ เพื่อใช้ให้มนุษย์เข้ามาแก้ไขต่อ |
| **`verified/`** | `legal_responsibility_hash_index.jsonl`<br>`dispatch_authorization_hash_index.jsonl` | **ข้อมูลยืนยันเด็ดขาด (Verified):**<br>• จะมีข้อมูลเป็น 0 เสมอ จนกว่านิติกรหรือเจ้าหน้าที่ตรวจอนุมัติหลักฐานความรับผิดชอบอย่างเป็นทางการ (ระบบจะไม่ตัดสินใจให้เองโดยพลการ) |

---


## อัปเดตข้อมูลระดับน้ำ

### รันด้วยมือ (ครั้งเดียว)

ดับเบิลคลิก `update.bat` หรือรันใน Command Prompt:

```bat
D:\Floodtir\Floodtir\update.bat
```

script จะ:
1. ดึงข้อมูลล่าสุดจาก `weather.bangkok.go.th` (BMA)
2. Rebuild `flood_bkk_map.html` พร้อมข้อมูลใหม่

ดู log ได้ที่ `update.log`

---

### ตั้งค่าอัปเดตอัตโนมัติทุก 5 นาที (Task Scheduler)

เปิด **Command Prompt แบบ Administrator** แล้วรัน:

```bat
schtasks /create /tn "FloodtirUpdate" /tr "D:\Floodtir\Floodtir\update.bat" /sc MINUTE /mo 5 /ru "%USERNAME%" /f
```

ตรวจสอบว่า task ทำงานอยู่:

```bat
schtasks /query /tn "FloodtirUpdate"
```

ลบ task:

```bat
schtasks /delete /tn "FloodtirUpdate" /f
```

> **หมายเหตุ:** ข้อมูลจะสดก็ต่อเมื่อ refresh browser หลัง update.bat รันเสร็จ

---

## Rebuild แผนที่ด้วยมือ

ถ้าแก้ไข `templates/_head.html` หรือ `templates/_foot.html` แล้วต้องการ rebuild:

```bat
cd D:\Floodtir\Floodtir\scripts
python build_map.py
```

ถ้าแก้ไข JavaScript logic ของแผนที่ ให้แก้ที่ `templates/_foot.html` เสมอ — อย่าแก้ `flood_bkk_map.html` ตรงๆ เพราะไฟล์นั้น generate อัตโนมัติและจะถูก overwrite ทุกครั้ง

---

## เพิ่ม/อัปเดต water edge network

ถ้าต้องการ rebuild `water_edges_geojson.json` (เช่น หลัง catalog สถานีเปลี่ยน):

```bat
cd D:\Floodtir\Floodtir\scripts
python build_water_artifacts.py
```

จะ rebuild ไฟล์ใน `water-data/` ทั้งหมด รวม edge network และ viz payload

---

## สร้าง Responsibility Hash Index

สร้าง index สำหรับค้นหาหน่วยงานที่ควรรับเรื่องจากพิกัดน้ำท่วม:

```bash
python3 scripts/build_responsibility_index.py
```

ทดลองค้นหาพิกัด:

```bash
python3 scripts/build_responsibility_index.py --query 13.7563 100.5018
```

ผลลัพธ์อยู่ใน `data/responsibility/` โดยแยก `acquisition/`, `candidate/`,
`inputs/`, `review/`, `security/` และ `verified/` ออกจากกัน รายละเอียดอยู่ที่
`docs/RESPONSIBILITY_INDEX.md` และสถานะพร้อมข้อจำกัดสำหรับ handoff อยู่ที่
`docs/RESPONSIBILITY_HASH_INDEX_STATUS.md`

> ทุก assignment เป็น operational candidate และยังไม่ใช่ข้อสรุปความรับผิด
> ทางกฎหมาย `verified/` จะไม่รับข้อมูลจาก candidate อัตโนมัติ ต้องมี
> เจ้าหน้าที่หรือนิติกรตรวจหลักฐานก่อนนำไปสั่งการ

---

## แหล่งข้อมูล

| ข้อมูล | แหล่ง | อัปเดต |
|--------|--------|--------|
| ระดับน้ำในคลอง (301 สถานี) | สำนักการระบายน้ำ กทม. — `weather.bangkok.go.th` | ทุก 5 นาที |
| เส้นคลอง, ประตูน้ำ, ท่อระบายน้ำ | BMA SEDGIS — `bmasedgis.bangkok.go.th` | static |
| จุดเสี่ยงน้ำท่วม 473 จุด | กทม. | static |
| น้ำท่วมถนน | BMA Thaiwater | near real-time |

ท่อระบายน้ำ (drainage pipes) ดึง live จาก BMA FeatureServer เมื่อ zoom level ≥ 15 เท่านั้น — ถ้า server กทม. ล่มจะแสดง error ใน layer นั้น

---

## ข้อมูลระดับน้ำในคลอง — ทำงานยังไง

เมื่อคลิกที่คลองใดๆ ระบบจะหาระดับน้ำโดย:

1. **ค้นหาชื่อคลองใน water edge network** — ถ้าพบ จะใช้ค่าเฉลี่ยระดับน้ำจากสถานีวัดในคลองนั้น (แม่นที่สุด)
2. **ถ้าไม่พบ** — จะใช้สถานีที่ใกล้ที่สุดใน radius 5.5 กม. แทน (proximity fallback)

> edge network มีข้อมูลเฉพาะคลองที่มีสถานีวัดน้ำของ กทม. (~55 คลอง/แม่น้ำ) คลองที่เหลือจะใช้ proximity matching

---

## ความต้องการของระบบ

- **Python:** MSYS2 Python 3 (`C:\msys64\ucrt64\bin\python3.exe`)
- **ไลบรารี Python:** ใช้ standard library ล้วน ไม่ต้องติดตั้งเพิ่ม
- **Browser:** Chrome / Firefox / Edge (ไม่รองรับ IE)
- **Internet:** ต้องการสำหรับ `update.bat` และ drainage pipes LIVE layer

---

## ปัญหาที่พบบ่อย

**`update.bat` ขึ้น SSL error**
> ใช้ `scripts/run_scraper.py` เป็น wrapper แก้ปัญหา SSL cert ของ MSYS2 Python บน Windows ไม่ต้องแก้อะไรเพิ่ม — ถ้ายังไม่ได้ลองรัน `update.bat` เองก่อน

**คลองไม่มีข้อมูลระดับน้ำ (popup ขึ้น "ไม่มีข้อมูล")**
> คลองนั้นอยู่นอก coverage 5.5 กม. ของสถานีวัดน้ำใดๆ หรือสถานีใกล้สุดออฟไลน์

**ท่อระบายน้ำไม่โหลด**
> server BMA ล่ม หรือ CORS block — layer นี้ต้องการ server กทม. ตลอดเวลา

**ข้อมูลระดับน้ำเก่า**
> รัน `update.bat` แล้ว refresh browser ใหม่ ข้อมูลจะสด

**`build_map.py` ขึ้น path error**
> ต้องรันจาก `scripts/` เสมอ:
> ```bat
> cd D:\Floodtir\Floodtir\scripts
> python build_map.py
> ```

---

## โครงสร้างข้อมูลเครือข่ายระบายน้ำ (Canal Graph Data Structure)

ไฟล์ `scripts/graph_data.js` เก็บข้อมูลเครือข่ายกราฟระบายน้ำทั้งหมดในตัวแปร `window.GRAPH` ซึ่งได้รับการออกแบบโครงสร้างข้อมูลให้บราวเซอร์และสคริปต์ต่างๆ เรียกใช้ผ่านอัลกอริทึมได้ง่ายและเร็วที่สุด ($O(1)$ lookup):

```javascript
window.GRAPH = {
  // 1. ข้อมูลโหนดและพิกัดภูมิศาสตร์ดั้งเดิม (รูปแบบ Array)
  "nodes": [ { "id": "N_0", "type": "junction", "pt": [100.54, 13.71], ... } ],
  "poi_nodes": [ { "id": "POI_GATE_0", "type": "gate", "pt": [100.54, 13.71], "linked": "N_0", ... } ],
  "edges": [ { "id": "E_0", "s": "N_0", "t": "N_1", ... } ],

  // 2. แผนผังการเชื่อมโยงทิศทางเดียว (Adjacency Map)
  // ช่วยให้อัลกอริทึมค้นหาเส้นทางระบายน้ำ (เช่น Dijkstra/BFS) ดึงโหนดข้างเคียงของโหนดใดๆ ได้ทันทีโดยไม่ต้องวนลูป edges
  "adjacency": {
    "N_0": ["N_1", "N_2"],
    "N_1": ["N_3"]
  },

  // 3. ดัชนีตารางกริดพื้นที่ (Spatial Hash Grid Index)
  // แบ่งแผนที่เป็นตารางขนาด 0.01 x 0.01 องศา (~1.1 กม.) ช่วยให้การสืบค้นหาพิกัดหรือการ Snap อุปกรณ์ระบายน้ำใกล้ตัว
  // ทำงานด้วยความเร็วระดับ O(1) เฉลี่ย (ประมวลผลระยะห่างเฉพาะโหนดในกล่องตาราง 3x3 แทนการวนลูปเทียบจุดทั้งหมดใน กทม.)
  "spatial_grid": {
    "100.54,13.71": ["N_0", "N_10"]
  }
};
```

---

## Pipeline โดยย่อ

```
weather.bangkok.go.th
        │
        ▼ scrape_bangkok_water.py (ทุก 5 นาที)
        │
water-data/water_latest_snapshot.json
        │
        ▼ build_map.py
        │
flood_bkk_map.html  ←── templates/ (_head + _foot + bkk_data.js)
                    ←── water-data/ (snapshot + edges)
                    ←── data/geojson/canals_chunks/ (lazy loaded)
```

---

## 🐒 ข้อมูลแผนที่เขตแบบเข้าใจง่าย (District Info & Clicking)


### ข้อมูลดัชนีเขตและไฟล์คลอง (Index.json คืออะไร?)
เนื่องจากข้อมูลคลองมันเยอะมาก เราเลยหั่นข้อมูลคลองแยกออกเป็นไฟล์ย่อยๆ ตามเขต เก็บไว้ในโฟลเดอร์ `data/geojson/canals_chunks/` โดยมีพี่เบิ้ม [index.json](file:///d:/Floodtir/Floodtir/data/geojson/canals_chunks/index.json) คอยบอกทางว่าเขตไหนอยู่ไฟล์ไหน:

```json
{
  "สาทร": {
    "bbox": [13.70, 100.51, 13.72, 100.54], // กรอบพิกัดของเขต
    "file": "c0.json"                        // ไฟล์เก็บข้อมูลคลองในเขตสาทร
  }
}
```

- **อยากรู้ว่าไฟล์ไหน (`c0.json`) เป็นของเขตอะไร?** 
  - ให้ดูที่กุญแจชื่อเขต (Key) ในไฟล์ `index.json`
  - ตัวอย่างโค้ดสั้นๆ เผื่ออยากเอาไปใช้ต่อ:
    - **JavaScript**: `const district = Object.keys(canalIndex).find(k => canalIndex[k].file === 'c0.json');` (ได้ผลลัพธ์เป็น `"สาทร"`)
    - **Python**: `district = next(k for k, v in index.items() if v['file'] == 'c0.json')`
