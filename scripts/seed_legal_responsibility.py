#!/usr/bin/env python3
import argparse
import asyncio
import json
from pathlib import Path
from sqlalchemy import text
from api.database import AsyncSessionLocal

async def seed_legal_responsibility(source_dir: Path, clear: bool):
    async with AsyncSessionLocal() as db:
        print("Connecting to DB...")
        
        if clear:
            print("Clearing existing legal responsibility data from SQL (CASCADE)...")
            await db.execute(text("TRUNCATE TABLE agency, legal_provision, district_authority_candidate, dispatch_guardrail, legal_review_task CASCADE"))
            await db.commit()
            print("Existing data cleared.")

        # 1. Seed Agencies
        agency_file = source_dir / "candidate" / "agency_master.json"
        if agency_file.exists():
            print("Seeding agencies...")
            with open(agency_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            agencies = data.get("agencies", [])
            print(f"Importing {len(agencies)} agencies...")
            
            # agency_master is already topologically sorted (parents before children)
            for idx, agency in enumerate(agencies):
                agency_id = agency.get("agency_id")
                name_th = agency.get("agency_name_th")
                name_en = agency.get("agency_name_en")
                agency_type = agency.get("agency_category")
                parent_agency_id = agency.get("parent_agency_id")
                
                await db.execute(
                    text("""
                        INSERT INTO agency (id, name_th, name_en, agency_type, parent_agency_id, is_simulated)
                        VALUES (:id, :name_th, :name_en, :agency_type, :parent_agency_id, FALSE)
                    """),
                    {
                        "id": agency_id,
                        "name_th": name_th,
                        "name_en": name_en,
                        "agency_type": agency_type,
                        "parent_agency_id": parent_agency_id
                    }
                )
                if idx % 20 == 0:
                    await db.commit()
            await db.commit()
            print("Agencies seeded successfully.")
        else:
            print(f"File not found: {agency_file}")

        # 2. Seed Legal Provisions
        provisions_file = source_dir / "legal_authority" / "authority_provisions_hash_index.jsonl"
        if provisions_file.exists():
            print("Seeding legal provisions...")
            count = 0
            with open(provisions_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    item = json.loads(line)
                    
                    await db.execute(
                        text("""
                            INSERT INTO legal_provision (
                                provision_hash, source_id, provision_reference, authority_type, 
                                territorial_scope, action_codes, requires_action_specific_order, 
                                may_auto_dispatch, is_simulated
                            )
                            VALUES (
                                :provision_hash, :source_id, :provision_reference, :authority_type, 
                                :territorial_scope, :action_codes, :requires_action_specific_order, 
                                :may_auto_dispatch, FALSE
                            )
                        """),
                        {
                            "provision_hash": item.get("authority_hash_sha256"),
                            "source_id": item.get("source_id"),
                            "provision_reference": item.get("section"),
                            "authority_type": item.get("authority_type"),
                            "territorial_scope": item.get("authority_scope"),
                            "action_codes": json.dumps(item.get("action_codes", [])),
                            "requires_action_specific_order": item.get("requires_action_specific_order", False),
                            "may_auto_dispatch": item.get("may_auto_dispatch", False)
                        }
                    )
                    count += 1
                    if count % 20 == 0:
                        await db.commit()
            await db.commit()
            print(f"Seeded {count} legal provisions successfully.")
        else:
            print(f"File not found: {provisions_file}")

        # 3. Seed District Authority Candidates
        district_auth_file = source_dir / "legal_authority" / "district_authority_candidates.jsonl"
        if district_auth_file.exists():
            print("Seeding district authority candidates...")
            count = 0
            with open(district_auth_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    item = json.loads(line)
                    
                    await db.execute(
                        text("""
                            INSERT INTO district_authority_candidate (
                                district, role, authority_provision_hashes, is_simulated
                            )
                            VALUES (
                                :district, :role, :authority_provision_hashes, FALSE
                            )
                        """),
                        {
                            "district": item.get("district_name_th"),
                            "role": item.get("actor_role_code"),
                            "authority_provision_hashes": json.dumps(item.get("authority_provision_hashes_sha256", []))
                        }
                    )
                    count += 1
                    if count % 20 == 0:
                        await db.commit()
            await db.commit()
            print(f"Seeded {count} district authority candidates successfully.")
        else:
            print(f"File not found: {district_auth_file}")

        # 4. Seed Dispatch Guardrails
        guardrails_file = source_dir / "legal_authority" / "dispatch_guardrails.json"
        if guardrails_file.exists():
            print("Seeding dispatch guardrails...")
            with open(guardrails_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            allowed = data.get("allowed_before_legal_approval", [])
            prohibited = data.get("prohibited_without_verified_action_specific_authorization", [])
            
            print(f"Importing {len(allowed)} allowed & {len(prohibited)} prohibited action guardrails...")
            
            count = 0
            for action in allowed:
                await db.execute(
                    text("""
                        INSERT INTO dispatch_guardrail (action_code, is_prohibited_without_auth, is_allowed_before_approval, is_simulated)
                        VALUES (:action_code, FALSE, TRUE, FALSE)
                        ON CONFLICT (action_code) DO NOTHING
                    """),
                    {"action_code": action}
                )
                count += 1
                
            for action in prohibited:
                await db.execute(
                    text("""
                        INSERT INTO dispatch_guardrail (action_code, is_prohibited_without_auth, is_allowed_before_approval, is_simulated)
                        VALUES (:action_code, TRUE, FALSE, FALSE)
                        ON CONFLICT (action_code) DO NOTHING
                    """),
                    {"action_code": action}
                )
                count += 1
                
            await db.commit()
            print(f"Seeded {count} dispatch guardrails successfully.")
        else:
            print(f"File not found: {guardrails_file}")

        # 5. Seed Legal Review Tasks
        review_queue_file = source_dir / "legal_authority" / "legal_review_queue.jsonl"
        if review_queue_file.exists():
            print("Seeding legal review tasks...")
            count = 0
            with open(review_queue_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    item = json.loads(line)
                    
                    await db.execute(
                        text("""
                            INSERT INTO legal_review_task (
                                task_id, review_type, source_id, provision_id, 
                                review_question, required_reviewer_role, status, is_simulated
                            )
                            VALUES (
                                :task_id, :review_type, :source_id, :provision_id, 
                                :review_question, :required_reviewer_role, :status, FALSE
                            )
                        """),
                        {
                            "task_id": item.get("legal_review_hash_sha256"),
                            "review_type": item.get("review_type"),
                            "source_id": item.get("source_id"),
                            "provision_id": item.get("provision_id"),
                            "review_question": item.get("review_question"),
                            "required_reviewer_role": item.get("required_reviewer_role"),
                            "status": item.get("review_status", "open")
                        }
                    )
                    count += 1
                    if count % 20 == 0:
                        await db.commit()
            await db.commit()
            print(f"Seeded {count} legal review tasks successfully.")
        else:
            print(f"File not found: {review_queue_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="Clear existing data before seeding")
    parser.add_argument("--source-dir", type=str, default="D:\\Floodtir\\Tanu\\floodtir\\Floodtirdatta\\data\\responsibility", help="Directory containing JSON/JSONL files")
    args = parser.parse_args()
    
    asyncio.run(seed_legal_responsibility(Path(args.source_dir), args.clear))
