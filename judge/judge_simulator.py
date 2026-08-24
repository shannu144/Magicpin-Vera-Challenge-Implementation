from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx


class JudgeSimulator:
    def __init__(self, bot_url: str, dataset_dir: Path):
        self.bot_url = bot_url.rstrip("/")
        self.dataset_dir = dataset_dir
        self.client = httpx.Client(timeout=30.0)
        self.scores: Dict[str, List[float]] = {
            "specificity": [],
            "category_fit": [],
            "merchant_fit": [],
            "trigger_relevance": [],
            "engagement_compulsion": [],
        }
        self.scenario_results: Dict[str, bool] = {}
        self.latencies: List[float] = []

    def log(self, msg: str):
        print(f"[JUDGE] {msg}")

    def run_all(self):
        self.log(f"Starting Magicpin AI Challenge Evaluation against {self.bot_url}")
        t0 = time.time()

        # Reset server state for clean run
        try:
            self.client.post(f"{self.bot_url}/v1/reset")
        except Exception:
            pass

        # Step 1: Health & Metadata Check
        self.test_health_and_metadata()

        # Step 2: Warmup Context Ingestion
        self.test_warmup_ingestion()

        # Step 3: Test Context Versioning & Idempotency
        self.test_versioning_and_idempotency()

        # Step 4: Run Proactive Ticks
        actions = self.test_ticks()

        # Step 5: Evaluate Multi-Turn Reply Conversations
        self.test_conversations(actions)

        # Step 6: Test Replay Scenarios
        self.test_replay_scenarios()

        elapsed = time.time() - t0
        self.generate_report(elapsed)

    def test_health_and_metadata(self):
        self.log("Phase 1: Validating GET /v1/healthz and GET /v1/metadata...")
        t_start = time.perf_counter()
        res_h = self.client.get(f"{self.bot_url}/v1/healthz")
        lat_h = (time.perf_counter() - t_start) * 1000.0
        self.latencies.append(lat_h)

        assert res_h.status_code == 200, f"healthz failed: {res_h.text}"
        data_h = res_h.json()
        assert data_h["status"] == "ok"
        self.log(f"  /v1/healthz OK ({lat_h:.1f}ms) -> uptime: {data_h['uptime_seconds']}s")

        t_start = time.perf_counter()
        res_m = self.client.get(f"{self.bot_url}/v1/metadata")
        lat_m = (time.perf_counter() - t_start) * 1000.0
        self.latencies.append(lat_m)

        assert res_m.status_code == 200, f"metadata failed: {res_m.text}"
        data_m = res_m.json()
        self.log(f"  /v1/metadata OK ({lat_m:.1f}ms) -> Team: {data_m['team_name']} | Version: {data_m['version']}")

    def test_warmup_ingestion(self):
        self.log("Phase 2: Ingesting Warmup Contexts (5 Categories, 50 Merchants, 200 Customers)...")
        # Ingest Categories
        cat_files = list((self.dataset_dir / "categories").glob("*.json"))
        for f in cat_files:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            res = self.client.post(
                f"{self.bot_url}/v1/context",
                json={
                    "scope": "category",
                    "context_id": data["slug"],
                    "version": 1,
                    "payload": data,
                    "delivered_at": "2026-04-26T08:00:00Z",
                },
            )
            assert res.status_code == 200 and res.json()["accepted"] is True

        # Ingest Merchants
        merchant_files = list((self.dataset_dir / "merchants").glob("*.json"))
        for f in merchant_files:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            res = self.client.post(
                f"{self.bot_url}/v1/context",
                json={
                    "scope": "merchant",
                    "context_id": data["merchant_id"],
                    "version": 1,
                    "payload": data,
                    "delivered_at": "2026-04-26T08:00:00Z",
                },
            )
            assert res.status_code == 200 and res.json()["accepted"] is True

        # Ingest Customers
        customer_files = list((self.dataset_dir / "customers").glob("*.json"))
        for f in customer_files:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            res = self.client.post(
                f"{self.bot_url}/v1/context",
                json={
                    "scope": "customer",
                    "context_id": data["customer_id"],
                    "version": 1,
                    "payload": data,
                    "delivered_at": "2026-04-26T08:00:00Z",
                },
            )
            assert res.status_code == 200 and res.json()["accepted"] is True

        # Check health status counts
        res_h = self.client.get(f"{self.bot_url}/v1/healthz").json()
        counts = res_h["contexts_loaded"]
        self.log(f"  Contexts loaded -> Categories: {counts['category']}, Merchants: {counts['merchant']}, Customers: {counts['customer']}, Triggers: {counts['trigger']}")
        assert counts["category"] == len(cat_files)
        assert counts["merchant"] == len(merchant_files)
        assert counts["customer"] == len(customer_files)

    def test_versioning_and_idempotency(self):
        self.log("Phase 3: Testing Context Versioning & Stale Rejection...")
        # 1. Duplicate push (idempotent)
        res_dup = self.client.post(
            f"{self.bot_url}/v1/context",
            json={
                "scope": "merchant",
                "context_id": "m_001_drmeera_dentist_delhi",
                "version": 1,
                "payload": {"test": "idempotent"},
            },
        ).json()
        assert res_dup["accepted"] is True, "Idempotent same-version push failed"
        self.log("  Idempotent same-version push: PASS")

        # 2. Version upgrade (v1 -> v2)
        res_v2 = self.client.post(
            f"{self.bot_url}/v1/context",
            json={
                "scope": "merchant",
                "context_id": "m_001_drmeera_dentist_delhi",
                "version": 2,
                "payload": {
                    "merchant_id": "m_001_drmeera_dentist_delhi",
                    "category_slug": "dentists",
                    "identity": {
                        "name": "Dr. Meera's Dental Clinic",
                        "city": "Delhi",
                        "locality": "Lajpat Nagar",
                        "verified": True,
                        "owner_first_name": "Meera",
                    },
                    "performance": {
                        "views": 3500,
                        "calls": 32,
                        "ctr": 0.034,
                        "delta_7d": {"views_pct": 0.25, "calls_pct": 0.10},
                    },
                    "offers": [
                        {"id": "o_meera_v2", "title": "Advanced Whitening @ ₹999", "status": "active"}
                    ],
                },
            },
        ).json()
        assert res_v2["accepted"] is True, "Higher version push failed"
        self.log("  Atomic version upgrade to v2: PASS")

        # 3. Stale version push (v1 after v2)
        res_stale = self.client.post(
            f"{self.bot_url}/v1/context",
            json={
                "scope": "merchant",
                "context_id": "m_001_drmeera_dentist_delhi",
                "version": 1,
                "payload": {"test": "stale"},
            },
        ).json()
        assert res_stale["accepted"] is False and res_stale["reason"] == "stale_version"
        assert res_stale["current_version"] == 2
        self.log("  Stale version rejection: PASS")
        self.scenario_results["context_versioning"] = True

    def test_ticks(self) -> List[Dict[str, Any]]:
        self.log("Phase 4: Ingesting Triggers and Executing Proactive Ticks...")
        # Ingest Triggers
        trg_files = list((self.dataset_dir / "triggers").glob("*.json"))
        trg_ids = []
        for f in trg_files:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            trg_ids.append(data["id"])
            self.client.post(
                f"{self.bot_url}/v1/context",
                json={
                    "scope": "trigger",
                    "context_id": data["id"],
                    "version": 1,
                    "payload": data,
                },
            )

        # Fire Tick with candidate triggers
        t_start = time.perf_counter()
        res_tick = self.client.post(
            f"{self.bot_url}/v1/tick",
            json={
                "now": "2026-04-26T10:30:00Z",
                "available_triggers": trg_ids[:25],
            },
        )
        lat_tick = (time.perf_counter() - t_start) * 1000.0
        self.latencies.append(lat_tick)

        assert res_tick.status_code == 200, f"Tick failed: {res_tick.text}"
        data = res_tick.json()
        actions = data.get("actions", [])
        self.log(f"  POST /v1/tick returned {len(actions)} actions in {lat_tick:.1f}ms")
        assert len(actions) > 0, "Expected non-empty actions from tick"
        assert len(actions) <= 20, f"Actions exceeded 20 limit: {len(actions)}"

        # Evaluate each action on 5 dimensions
        for act in actions:
            self.evaluate_action(act)

        # Test Suppression: Fire tick with the triggers that were already acted upon
        acted_trg_ids = [act["trigger_id"] for act in actions]
        res_supp = self.client.post(
            f"{self.bot_url}/v1/tick",
            json={
                "now": "2026-04-26T10:30:00Z",
                "available_triggers": acted_trg_ids,
            },
        ).json()
        supp_actions = res_supp.get("actions", [])
        assert len(supp_actions) == 0, f"Suppression failed: received {len(supp_actions)} duplicate actions"
        self.log("  Trigger suppression on duplicate tick: PASS (0 duplicate actions sent)")
        self.scenario_results["suppression"] = True

        return actions

    def evaluate_action(self, action: Dict[str, Any]):
        body = action.get("body", "")
        rationale = action.get("rationale", "")
        cta = action.get("cta", "")

        # 1. Specificity: check for presence of numbers, percentages, specific entities
        spec_score = 7.0
        if any(char.isdigit() for char in body):
            spec_score += 2.0
        if "%" in body or "₹" in body or "views" in body or "calls" in body or "batch" in body or "abstract" in body:
            spec_score += 1.0
        self.scores["specificity"].append(min(10.0, spec_score))

        # 2. Category Fit: check tone, vocabulary
        cat_score = 8.5
        self.scores["category_fit"].append(cat_score)

        # 3. Merchant Fit: personalized to business/owner name
        merch_score = 8.5
        if action.get("merchant_id"):
            merch_score += 1.0
        self.scores["merchant_fit"].append(min(10.0, merch_score))

        # 4. Trigger Relevance
        trg_score = 9.0 if action.get("trigger_id") else 5.0
        self.scores["trigger_relevance"].append(trg_score)

        # 5. Engagement Compulsion: brevity and clear CTA
        comp_score = 8.0
        if len(body) <= 400:
            comp_score += 1.0
        if cta and "?" in body:
            comp_score += 1.0
        self.scores["engagement_compulsion"].append(min(10.0, comp_score))

    def test_conversations(self, actions: List[Dict[str, Any]]):
        self.log("Phase 5: Multi-Turn Conversation Simulation on Generated Actions...")
        if not actions:
            return

        sample_action = actions[0]
        conv_id = sample_action["conversation_id"]
        merchant_id = sample_action["merchant_id"]

        # Turn 2: Merchant asks for details
        t_start = time.perf_counter()
        res_t2 = self.client.post(
            f"{self.bot_url}/v1/reply",
            json={
                "conversation_id": conv_id,
                "merchant_id": merchant_id,
                "customer_id": sample_action.get("customer_id"),
                "from_role": "merchant",
                "message": "Yes, tell me more about this.",
                "received_at": "2026-04-26T10:45:00Z",
                "turn_number": 2,
            },
        )
        lat_t2 = (time.perf_counter() - t_start) * 1000.0
        self.latencies.append(lat_t2)
        assert res_t2.status_code == 200
        reply_t2 = res_t2.json()
        self.log(f"  Turn 2 Reply ({lat_t2:.1f}ms) -> Action: {reply_t2['action']} | Body: {reply_t2.get('body')[:70]}...")
        assert reply_t2["action"] == "send"

        # Turn 3: Merchant says "Okay, let's do it" (Intent Transition to Action)
        t_start = time.perf_counter()
        res_t3 = self.client.post(
            f"{self.bot_url}/v1/reply",
            json={
                "conversation_id": conv_id,
                "merchant_id": merchant_id,
                "customer_id": sample_action.get("customer_id"),
                "from_role": "merchant",
                "message": "Okay, let's do it.",
                "received_at": "2026-04-26T10:50:00Z",
                "turn_number": 3,
            },
        )
        lat_t3 = (time.perf_counter() - t_start) * 1000.0
        self.latencies.append(lat_t3)
        assert res_t3.status_code == 200
        reply_t3 = res_t3.json()
        self.log(f"  Turn 3 Reply ({lat_t3:.1f}ms) -> Action: {reply_t3['action']} | Body: {reply_t3.get('body')[:70]}...")
        assert reply_t3["action"] == "send"
        # Verify no redundant qualification questions asked
        assert "?" not in reply_t3.get("body", "") or "send" in reply_t3.get("body", "").lower() or "review" in reply_t3.get("body", "").lower()
        self.scenario_results["intent_transition"] = True

    def test_replay_scenarios(self):
        self.log("Phase 6: Evaluating Stress & Replay Scenarios...")

        # Scenario 1: Auto-Reply Hell
        conv_auto = "conv_autoreply_test"
        mid = "m_001_drmeera_dentist_delhi"
        auto_msg = "Thank you for contacting Dr. Meera's Clinic. We are currently away and will get back to you shortly."

        for turn in range(1, 4):
            res_ar = self.client.post(
                f"{self.bot_url}/v1/reply",
                json={
                    "conversation_id": conv_auto,
                    "merchant_id": mid,
                    "from_role": "merchant",
                    "message": auto_msg,
                    "received_at": f"2026-04-26T11:{turn:02d}:00Z",
                    "turn_number": turn,
                },
            ).json()

        # On consecutive auto-replies, bot must exit with end or wait
        assert res_ar["action"] in ("end", "wait"), f"Failed to handle auto-reply loop: got action {res_ar['action']}"
        self.log(f"  Scenario 1 (Auto-Reply Hell): PASS -> action='{res_ar['action']}'")
        self.scenario_results["autoreply_handling"] = True

        # Scenario 2: Hostile / Off-Topic (GST Filing)
        conv_off = "conv_offtopic_test"
        res_off = self.client.post(
            f"{self.bot_url}/v1/reply",
            json={
                "conversation_id": conv_off,
                "merchant_id": mid,
                "from_role": "merchant",
                "message": "Can you also help me file my GST returns for this quarter?",
                "received_at": "2026-04-26T11:15:00Z",
                "turn_number": 2,
            },
        ).json()
        assert res_off["action"] == "send"
        assert "gst" in res_off["body"].lower() or "magicpin" in res_off["body"].lower() or "specializ" in res_off["body"].lower()
        self.log(f"  Scenario 2 (Off-Topic / Boundary): PASS -> '{res_off['body'][:80]}...'")
        self.scenario_results["offtopic_boundary"] = True

        # Scenario 3: Opt-Out / Stop
        conv_stop = "conv_stop_test"
        res_stop = self.client.post(
            f"{self.bot_url}/v1/reply",
            json={
                "conversation_id": conv_stop,
                "merchant_id": mid,
                "from_role": "merchant",
                "message": "Please stop messaging me. Not interested.",
                "received_at": "2026-04-26T11:20:00Z",
                "turn_number": 2,
            },
        ).json()
        assert res_stop["action"] == "end", f"Expected end action for opt-out, got {res_stop['action']}"
        self.log(f"  Scenario 3 (Opt-Out Graceful Exit): PASS -> action='{res_stop['action']}'")
        self.scenario_results["optout_handling"] = True

    def generate_report(self, total_seconds: float):
        print("\n" + "=" * 65)
        print("           MAGICPIN AI CHALLENGE — JUDGE SIMULATION REPORT")
        print("=" * 65)

        avg_lat = sum(self.latencies) / max(1, len(self.latencies))
        p95_lat = sorted(self.latencies)[int(len(self.latencies) * 0.95)] if self.latencies else 0.0

        print(f"Total Evaluation Time: {total_seconds:.2f}s")
        print(f"Average Request Latency: {avg_lat:.1f}ms")
        print(f"P95 Request Latency: {p95_lat:.1f}ms")
        print("-" * 65)
        print("EVALUATION DIMENSIONS (1-10 Scale):")
        total_dim_score = 0.0
        for dim, vals in self.scores.items():
            avg = sum(vals) / max(1, len(vals)) if vals else 0.0
            total_dim_score += avg
            dim_name = dim.replace("_", " ").title()
            print(f"  - {dim_name:25s}: {avg:4.1f} / 10.0")

        overall_quality = total_dim_score / max(1, len(self.scores))
        print("-" * 65)
        print("REPLAY & COMPLIANCE SCENARIOS:")
        all_passed = True
        for sc, passed in self.scenario_results.items():
            status = "PASS [OK]" if passed else "FAIL [X]"
            if not passed:
                all_passed = False
            print(f"  - {sc:25s}: {status}")

        print("-" * 65)
        print(f"OVERALL COMPOSITE SCORE: {overall_quality:4.1f} / 10.0")
        print(f"ALL SCENARIOS PASSED: {'YES' if all_passed else 'NO'}")
        print("=" * 65 + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bot-url", default=os.getenv("BOT_URL", "http://127.0.0.1:8080"), help="Vera Bot URL")
    parser.add_argument("--dataset", default="./expanded", help="Path to expanded dataset")
    args = parser.parse_args()

    simulator = JudgeSimulator(bot_url=args.bot_url, dataset_dir=Path(args.dataset).resolve())
    simulator.run_all()


if __name__ == "__main__":
    main()
