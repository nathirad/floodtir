# Verified Responsibility Input

ไฟล์ในโฟลเดอร์นี้เป็นช่องรับข้อมูลที่เจ้าหน้าที่หรือนิติกรตรวจแล้วเท่านั้น
ตัวสร้าง index จะไม่ย้ายข้อมูลจาก `candidate/` มาเป็น `verified/` อัตโนมัติ

## ไฟล์รับข้อมูล

- `official_document_evidence.json`: หลักฐาน PDF, Mission Duty และ SOP
  ที่สกัดจากเอกสารทางการ แต่ยังเป็น `pending_legal_review` และไม่ถูกเลื่อน
  เข้า `verified/` อัตโนมัติ
- `legal_basis.csv`: เอกสารอำนาจหน้าที่ พร้อมหน้า/ข้อ, URL, SHA-256 ของไฟล์
  เอกสาร, ผู้ตรวจ, ผู้อนุมัติ และเวลาของทั้งสองขั้นตอน
- `verified_responsibility_assignments.csv`: ความสัมพันธ์ระหว่างพื้นที่หรือ
  ทรัพย์สิน เหตุการณ์ บทบาท หน่วยงาน และ `legal_basis_id`
- `verified_dispatch_authorizations.csv`: สิทธิ์ของ role ในหน่วยงานต้นทาง
  สำหรับส่งหรืออนุมัติงานไปยังหน่วยงานเป้าหมาย แยกตามเขตและประเภทเหตุ
- `asset_owner_evidence.csv`: หลักฐานผู้ดูแลทรัพย์สินระบายน้ำ ใช้ประกอบการ
  ตรวจและจัดทำ assignment
- `incident_responsibility_matrix.csv`: ตารางประเภทเหตุ/ระดับความรุนแรง/
  บทบาท ใช้ประกอบการตรวจและจัดทำ assignment

## กติกา

1. ใช้แหล่งทางการและ HTTPS
2. เก็บตำแหน่งหน้า ข้อ หรือมาตราที่อ้างอิงได้
3. คำนวณ SHA-256 จากไฟล์เอกสารฉบับที่ตรวจจริง
4. ระบุผู้ตรวจและผู้อนุมัติคนละคน พร้อมเวลาทุกแถว
5. ระบุ effective date และเหตุผลการเปลี่ยน assignment
6. ห้ามใส่ข้อมูลส่วนบุคคลของผู้แจ้งเหตุหรือประชาชน
7. การแก้ input ต้องผ่าน code review หรือ data review ก่อนนำไปใช้งาน

Dispatch authorization ใช้ `actor_role_code` ไม่ใช้ชื่อบุคคล และต้องอ้าง
`legal_basis_id` ที่ผ่านการตรวจแล้ว ระบบจะไม่สร้างสิทธิ์จาก Candidate
capability อัตโนมัติ

เมื่อ input ยังว่าง `verified/legal_responsibility_hash_index.jsonl` จะว่างตามไป
ด้วยโดยตั้งใจ
