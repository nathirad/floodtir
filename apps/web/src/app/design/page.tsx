import Link from "next/link";

export const metadata = {
  title: "System Storyboard — Floodtir Design",
};

const stages = [
  {
    step: "01",
    actor: "ประชาชน",
    title: "รายงานเหตุ",
    detail: "ภาพถ่าย + พิกัด + เวลา + คำอธิบาย",
    state: "UI TO DESIGN",
    tone: "border-gray-700 bg-gray-900",
  },
  {
    step: "02",
    actor: "AI ผู้ช่วยวิเคราะห์",
    title: "ประเมินจากภาพ",
    detail: "เสนอระดับน้ำและ confidence แต่ไม่มีสิทธิ์สั่งงาน",
    state: "PENDING-WIRE",
    tone: "border-purple-900 bg-purple-950/30",
  },
  {
    step: "03",
    actor: "Situation Model",
    title: "รวมหลายรายงาน",
    detail: "corroboration ≥ N ก่อนยกระดับเป็นสถานการณ์",
    state: "DEMO DATA",
    tone: "border-blue-900 bg-blue-950/30",
  },
  {
    step: "04",
    actor: "ผู้ประสานงาน",
    title: "ตรวจและอนุมัติ",
    detail: "เห็นหลักฐาน ความเสี่ยง และแผนที่ก่อนออก Work Order",
    state: "VISIBLE ON /",
    tone: "border-amber-900 bg-amber-950/30",
  },
  {
    step: "05",
    actor: "ฝ่ายปฏิบัติการ",
    title: "ยืนยันรับคำสั่ง",
    detail: "Human confirmation gate (G3) ก่อน dispatch ทุกครั้ง",
    state: "VISIBLE ON /",
    tone: "border-orange-900 bg-orange-950/30",
  },
  {
    step: "06",
    actor: "ประชาชน + ภาคสนาม",
    title: "ยืนยันผล",
    detail: "VERIFIED ปิดงาน · MISMATCH เปิดงานใหม่และวนซ้ำ",
    state: "DEMO INTERACTION",
    tone: "border-emerald-900 bg-emerald-950/30",
  },
  {
    step: "07",
    actor: "ผู้ตรวจสอบ",
    title: "ตรวจ Ledger",
    detail: "timeline จากหลักฐานพร้อม SHA-256 hash-chain",
    state: "VISIBLE ON /board",
    tone: "border-cyan-900 bg-cyan-950/30",
  },
];

const roles = [
  {
    role: "Citizen",
    need: "รายงานง่าย รู้ว่างานถึงไหน และยืนยันผลได้โดยไม่ต้องเข้า dashboard เจ้าหน้าที่",
    surfaces: "Report intake · Case status · Verify outcome",
    status: "ต้องออกแบบเพิ่ม",
  },
  {
    role: "Coordinator",
    need: "เห็นสถานการณ์ หลักฐาน และข้อเสนอแผน ก่อนกดยืนยันสร้างคำสั่ง",
    surfaces: "Situation Map · Work Order review",
    status: "มี Design Demo แล้ว",
  },
  {
    role: "Field Operations",
    need: "รับงานที่ชัดเจน ยืนยันรับคำสั่ง และส่งภาพผลงานกลับ",
    surfaces: "Dispatch inbox · Evidence upload",
    status: "มี flow บางส่วน",
  },
  {
    role: "Auditor / Public",
    need: "แยกข้อเท็จจริงออกจาก inference และตรวจย้อนหลังได้",
    surfaces: "Accountability Board",
    status: "มี Design Demo แล้ว",
  },
];

const boundaries = [
  "Claude Design แก้เฉพาะ apps/web และเอกสาร Design",
  "ไม่ต้องรันหรือแก้ apps/api, database, migrations, Docker หรือ seed scripts",
  "ข้อมูล /api/demo ทั้งหมดคือ SIMULATED-by-design",
  "ห้ามเปลี่ยน mock ให้ดูเหมือน PostGIS, ThaiWater, LINE หรือเจ้าหน้าที่จริง",
  "เมื่อ Backend พร้อมจึงตั้ง NEXT_PUBLIC_API_URL เพื่อสลับ API",
];

export default function DesignPage() {
  return (
    <main className="min-h-screen bg-gray-950 text-gray-100">
      <header className="sticky top-0 z-10 border-b border-gray-800 bg-gray-950/95 px-6 py-4 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-400">
              Frontend-only design reference
            </p>
            <h1 className="mt-1 text-xl font-semibold">
              Floodtir · System Storyboard
            </h1>
          </div>
          <nav className="flex items-center gap-2 text-xs">
            <Link
              href="/"
              className="rounded-md border border-gray-700 px-3 py-2 text-gray-300 hover:bg-gray-800"
            >
              Situation Map
            </Link>
            <Link
              href="/board"
              className="rounded-md border border-gray-700 px-3 py-2 text-gray-300 hover:bg-gray-800"
            >
              Accountability Board
            </Link>
          </nav>
        </div>
      </header>

      <div className="mx-auto max-w-7xl space-y-10 px-6 py-8">
        <section className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
          <div className="rounded-2xl border border-cyan-900 bg-cyan-950/20 p-6">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-orange-700 bg-orange-950 px-3 py-1 text-xs font-semibold text-orange-300">
                DESIGN DEMO
              </span>
              <span className="rounded-full border border-gray-700 bg-gray-900 px-3 py-1 text-xs text-gray-400">
                Backend untouched
              </span>
            </div>
            <h2 className="mt-5 text-2xl font-semibold">
              รับรู้ → สั่งการ → พิสูจน์ว่าทำจริง
            </h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-gray-400">
              หน้านี้เป็นแผนที่ความเข้าใจของผลิตภัณฑ์ ไม่ใช่หน้า production
              ใช้ให้ Claude Design เห็นทั้งระบบ บทบาทผู้ใช้ จุดที่มี UI แล้ว
              และจุดที่ยังต้องออกแบบ โดยไม่ต้องแตะ Backend
            </p>
          </div>

          <div className="rounded-2xl border border-gray-800 bg-gray-900 p-6">
            <p className="text-xs font-medium uppercase tracking-wider text-gray-500">
              Data truth legend
            </p>
            <div className="mt-4 space-y-3 text-sm">
              <div>
                <span className="font-semibold text-emerald-400">REAL</span>
                <p className="text-gray-500">ข้อมูลจริงที่มี source และ provenance</p>
              </div>
              <div>
                <span className="font-semibold text-orange-400">
                  SIMULATED-by-design
                </span>
                <p className="text-gray-500">ข้อมูล mock เพื่อประเมิน UX เท่านั้น</p>
              </div>
              <div>
                <span className="font-semibold text-gray-400">PENDING-WIRE</span>
                <p className="text-gray-500">ออกแบบไว้แต่ยังไม่เชื่อมระบบจริง</p>
              </div>
            </div>
          </div>
        </section>

        <section>
          <div className="mb-4">
            <p className="text-xs font-medium uppercase tracking-wider text-gray-500">
              End-to-end loop
            </p>
            <h2 className="mt-1 text-lg font-semibold">ภาพรวมระบบทั้งวงจร</h2>
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-7">
            {stages.map((stage, index) => (
              <article
                key={stage.step}
                className={`relative min-h-52 rounded-xl border p-4 ${stage.tone}`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-gray-600">
                    {stage.step}
                  </span>
                  {index < stages.length - 1 && (
                    <span className="hidden text-gray-700 xl:block">→</span>
                  )}
                </div>
                <p className="mt-5 text-[10px] font-semibold uppercase tracking-wider text-gray-500">
                  {stage.actor}
                </p>
                <h3 className="mt-1 font-semibold">{stage.title}</h3>
                <p className="mt-2 text-xs leading-5 text-gray-400">
                  {stage.detail}
                </p>
                <span className="absolute bottom-4 left-4 rounded bg-black/30 px-2 py-1 font-mono text-[9px] text-gray-400">
                  {stage.state}
                </span>
              </article>
            ))}
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
          <div>
            <div className="mb-4">
              <p className="text-xs font-medium uppercase tracking-wider text-gray-500">
                Role coverage
              </p>
              <h2 className="mt-1 text-lg font-semibold">
                Claude Design ต้องมองผ่านผู้ใช้ 4 กลุ่ม
              </h2>
            </div>
            <div className="overflow-hidden rounded-xl border border-gray-800">
              {roles.map((item) => (
                <div
                  key={item.role}
                  className="grid gap-3 border-b border-gray-800 bg-gray-900 p-4 last:border-b-0 md:grid-cols-[140px_1fr_220px]"
                >
                  <div>
                    <p className="font-semibold text-cyan-300">{item.role}</p>
                    <p className="mt-1 text-[10px] uppercase tracking-wider text-gray-600">
                      {item.status}
                    </p>
                  </div>
                  <p className="text-sm leading-6 text-gray-400">{item.need}</p>
                  <p className="font-mono text-xs leading-5 text-gray-500">
                    {item.surfaces}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <aside>
            <div className="mb-4">
              <p className="text-xs font-medium uppercase tracking-wider text-gray-500">
                Hard boundary
              </p>
              <h2 className="mt-1 text-lg font-semibold">
                สิ่งที่ไม่ให้ Claude Design แตะ
              </h2>
            </div>
            <div className="rounded-xl border border-red-950 bg-red-950/20 p-5">
              <ul className="space-y-3 text-sm leading-6 text-gray-400">
                {boundaries.map((boundary) => (
                  <li key={boundary} className="flex gap-3">
                    <span className="text-red-400">×</span>
                    <span>{boundary}</span>
                  </li>
                ))}
              </ul>
            </div>
          </aside>
        </section>

        <section className="rounded-2xl border border-gray-800 bg-gray-900 p-6">
          <p className="text-xs font-medium uppercase tracking-wider text-gray-500">
            Non-negotiable guardrails
          </p>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <div>
              <span className="font-mono text-blue-400">G3</span>
              <p className="mt-1 text-sm text-gray-400">
                ต้องมีมนุษย์ยืนยันก่อน dispatch เสมอ
              </p>
            </div>
            <div>
              <span className="font-mono text-blue-400">G7</span>
              <p className="mt-1 text-sm text-gray-400">
                รายงานเดียวไม่พอ ต้องมี corroboration ≥ N
              </p>
            </div>
            <div>
              <span className="font-mono text-blue-400">G9</span>
              <p className="mt-1 text-sm text-gray-400">
                Accountability Board แสดงเฉพาะ ledger-backed facts
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
