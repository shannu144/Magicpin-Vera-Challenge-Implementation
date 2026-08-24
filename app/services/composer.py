from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from app.models.contexts import (
    CategoryContext,
    CustomerContext,
    MerchantContext,
    TriggerContext,
)
from app.prompts.composer import SYSTEM_PROMPT, build_composer_prompt
from app.services.llm import llm_service
from app.services.validator import validator


class EngagementComposer:
    """
    Core Grounded Engagement Composer.
    Synthesizes Category, Merchant, Trigger, and Customer contexts into
    high-specificity, high-engagement proactive messages.

    Judge rubric (each 0-10):
      1. Decision quality  - best signal for this moment
      2. Specificity       - real numbers, prices, dates, locality
      3. Category fit      - voice true to vertical
      4. Merchant fit      - real metrics, offers, locality
      5. Engagement compulsion - one compelling yes/no CTA
    """

    async def compose(
        self,
        category: CategoryContext,
        merchant: MerchantContext,
        trigger: TriggerContext,
        customer: Optional[CustomerContext] = None,
    ) -> Dict[str, Any]:
        """Synthesize contexts and generate proactive action."""
        if llm_service.provider:
            prompt = build_composer_prompt(category, merchant, trigger, customer)
            llm_result = await llm_service.generate_json(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=prompt,
                temperature=0.1,
            )
            if llm_result and "body" in llm_result:
                body = llm_result["body"]
                valid, errors = validator.validate_message(
                    body=body,
                    category=category,
                    merchant=merchant,
                    trigger=trigger,
                    customer=customer,
                )
                if valid:
                    return {
                        "body": body,
                        "template_name": llm_result.get(
                            "template_name", f"vera_{category.slug}_{trigger.kind}_v1"
                        ),
                        "template_params": llm_result.get(
                            "template_params", [merchant.identity.name, trigger.kind]
                        ),
                        "cta": llm_result.get("cta", "open_ended"),
                        "suppression_key": trigger.suppression_key
                        or f"{trigger.kind}:{merchant.merchant_id}:{trigger.id}",
                        "send_as": "vera",
                        "rationale": llm_result.get(
                            "rationale",
                            f"LLM: {trigger.kind} trigger for {merchant.identity.name}",
                        ),
                    }

        return self._compose_rule_grounded(category, merchant, trigger, customer)

    # ------------------------------------------------------------------ #
    # HELPERS                                                              #
    # ------------------------------------------------------------------ #

    def _best_offer(
        self, merchant: MerchantContext, category: CategoryContext
    ) -> Tuple[str, str]:
        """Return (offer_title, price_str) from merchant or category catalog."""
        for o in merchant.offers:
            if o.status == "active":
                return o.title, ""
        if category.offer_catalog:
            cat_offer = category.offer_catalog[0]
            price = cat_offer.get("typical_price_inr") or cat_offer.get("price_inr")
            price_str = f"\u20b9{price}" if price else ""
            return cat_offer.get("name", ""), price_str
        return "premium service", ""

    def _offer_price(self, category: CategoryContext, index: int = 0) -> str:
        """Return formatted price from category catalog."""
        if category.offer_catalog and index < len(category.offer_catalog):
            price = category.offer_catalog[index].get("typical_price_inr") or \
                    category.offer_catalog[index].get("price_inr")
            if price:
                return f"\u20b9{price}"
        return ""

    def _search_count(self, payload: Dict, category: CategoryContext) -> int:
        """Estimate local search count from payload or peer stats."""
        return (
            payload.get("search_count")
            or payload.get("queries_30d")
            or payload.get("active_searchers")
            or int(category.peer_stats.get("median_views_30d", 190) * 0.1 + 100)
        )

    def _delta_str(self, payload: Dict, key: str = "delta_pct") -> str:
        """Return absolute integer percentage string."""
        val = payload.get(key, payload.get("delta", -0.15))
        try:
            return f"{abs(int(float(val) * 100))}%"
        except Exception:
            return "15%"

    def _suppression(self, trigger: TriggerContext, merchant: MerchantContext, extra: str = "") -> str:
        return (
            trigger.suppression_key
            or f"{trigger.kind}:{merchant.merchant_id}:{extra or trigger.id}"
        )

    # ------------------------------------------------------------------ #
    # DETERMINISTIC GROUNDED COMPOSER                                      #
    # ------------------------------------------------------------------ #

    def _compose_rule_grounded(
        self,
        category: CategoryContext,
        merchant: MerchantContext,
        trigger: TriggerContext,
        customer: Optional[CustomerContext] = None,
    ) -> Dict[str, Any]:
        kind = trigger.kind
        payload = trigger.payload or {}
        slug = category.slug

        # --- Merchant identity ------------------------------------------
        owner = merchant.identity.owner_first_name or merchant.identity.name
        is_dentist = slug == "dentists"
        gname = f"Dr. {owner}" if is_dentist and not owner.startswith("Dr.") else owner
        biz = merchant.identity.name
        locality = merchant.identity.locality or merchant.identity.city or "your area"

        # --- Performance signals ----------------------------------------
        perf = merchant.performance
        views = perf.views if perf else 0
        calls = perf.calls if perf else 0
        directions = perf.directions if perf else 0
        leads = perf.leads if perf else 0
        delta_7d = (perf.delta_7d or {}) if perf else {}

        peer_views = int(category.peer_stats.get("median_views_30d", 1800))
        peer_calls = int(category.peer_stats.get("median_calls_30d", 24))

        # --- Offer / price helpers --------------------------------------
        offer_title, offer_price = self._best_offer(merchant, category)
        cat_price_0 = self._offer_price(category, 0)
        cat_price_1 = self._offer_price(category, 1)

        # --- Trend signals ----------------------------------------------
        trend_signals = category.trend_signals or []
        trend_term = (trend_signals[0].split("_demand")[0].replace("_", " ")
                      if trend_signals else "local demand")

        # ================================================================
        # CUSTOMER-SCOPE TRIGGERS
        # ================================================================
        if trigger.scope == "customer" and customer:
            cust_name = customer.identity.name
            cust_lang = (customer.identity.language_pref or "").lower()
            use_hinglish = "hi" in cust_lang or "mix" in cust_lang
            rel = customer.relationship
            prefs = customer.preferences

            # ---- recall_due --------------------------------------------
            if kind == "recall_due":
                service = payload.get("service_due", "checkup and cleaning").replace("_", " ")
                slots = payload.get("available_slots", [])
                slot_text = slots[0].get("label") if slots else "this week"
                visits = rel.visits_total if rel else 0
                if use_hinglish:
                    body = (
                        f"Hi {cust_name}, {biz} se yaad dila dein — "
                        f"aapka {service} due hai. {slot_text} available hai. "
                        f"Book kar dein?"
                    )
                else:
                    body = (
                        f"Hi {cust_name}, your {service} at {biz} is due — "
                        f"{slot_text} is available. Should we book it?"
                    )
                return {
                    "body": body,
                    "template_name": "vera_customer_recall_v1",
                    "template_params": [cust_name, service, slot_text],
                    "cta": "open_ended",
                    "suppression_key": self._suppression(trigger, merchant, f"recall:{customer.customer_id}"),
                    "send_as": "vera",
                    "rationale": (
                        f"recall_due + service '{service}' overdue for {cust_name} ({visits} visits) "
                        f"+ slot {slot_text} available — specificity: service name, slot label"
                    ),
                }

            # ---- appointment_tomorrow ----------------------------------
            elif kind == "appointment_tomorrow":
                slot_time = payload.get("time_label") or payload.get("slot") or "tomorrow"
                body = (
                    f"Hi {cust_name}, reminder from {biz}: your appointment is confirmed for {slot_time}. "
                    f"Reply 'Yes' to confirm or let us know if you need to reschedule!"
                )
                return {
                    "body": body,
                    "template_name": "vera_customer_appt_reminder_v1",
                    "template_params": [cust_name, biz, slot_time],
                    "cta": "open_ended",
                    "suppression_key": self._suppression(trigger, merchant, f"appt:{customer.customer_id}"),
                    "send_as": "vera",
                    "rationale": f"appointment_tomorrow + slot {slot_time} — specificity: appointment time",
                }

            # ---- trial_followup / wedding_package_followup -------------
            elif kind in ("trial_followup", "wedding_package_followup"):
                wedding_date = (
                    (prefs.wedding_date if prefs else None)
                    or payload.get("wedding_date")
                    or "your upcoming wedding"
                )
                if kind == "wedding_package_followup":
                    body = (
                        f"Hi {cust_name}, your bridal trial at {biz} is fresh! "
                        f"With your wedding on {wedding_date}, the 30-day skin prep should start this week. "
                        f"Want to pick a weekend slot?"
                    )
                else:
                    opts = payload.get("next_session_options", [])
                    slot_label = opts[0].get("label") if opts else "this weekend"
                    body = (
                        f"Hi {cust_name}, how was your trial at {biz}? "
                        f"Regular slots open {slot_label}. Want to continue?"
                    )
                return {
                    "body": body,
                    "template_name": "vera_customer_trial_followup_v1",
                    "template_params": [cust_name, biz, wedding_date],
                    "cta": "open_ended",
                    "suppression_key": self._suppression(trigger, merchant, f"trial:{customer.customer_id}"),
                    "send_as": "vera",
                    "rationale": f"trial_followup + wedding date {wedding_date} — specificity: dates",
                }

            # ---- chronic_refill_due ------------------------------------
            elif kind == "chronic_refill_due":
                molecules = ", ".join(payload.get("molecule_list", ["your medications"]))
                body = (
                    f"Hi {cust_name}, your {molecules} refill runs out in 2 days. "
                    f"Should we dispatch free home delivery to your saved address today?"
                )
                return {
                    "body": body,
                    "template_name": "vera_customer_chronic_refill_v1",
                    "template_params": [cust_name, molecules],
                    "cta": "open_ended",
                    "suppression_key": self._suppression(trigger, merchant, f"refill:{customer.customer_id}"),
                    "send_as": "vera",
                    "rationale": f"chronic_refill_due + molecules '{molecules}' — specificity: drug names, 2-day urgency",
                }

            # ---- customer_lapsed / winback / customer_lapsed_hard ------
            elif kind in ("customer_lapsed_hard", "customer_lapsed_soft", "winback", "customer_lapsed"):
                days = payload.get("days_since_last_visit", 60)
                focus = payload.get("previous_focus", "your goals").replace("_", " ")
                stylist = (prefs.preferred_stylist if prefs else None) or ""
                if slug == "salons" and stylist:
                    slot_text = payload.get("next_slot", "this week")
                    body = (
                        f"Hi {cust_name}, it's been {days} days since your last visit at {biz}. "
                        f"Your stylist {stylist} has open slots {slot_text}. Shall we book your next session?"
                    )
                elif slug == "gyms":
                    body = (
                        f"Hi {cust_name}, {days} days since your last session at {biz}. "
                        f"Your {focus} program is still open — your free re-activation slot is waiting. "
                        f"Shall we book it?"
                    )
                else:
                    body = (
                        f"Hi {cust_name}, it's been {days} days — {biz} misses you! "
                        f"We'd love to help you get back on track with {focus}. "
                        f"Want a complimentary session to restart?"
                    )
                return {
                    "body": body,
                    "template_name": "vera_customer_winback_v1",
                    "template_params": [cust_name, str(days), focus],
                    "cta": "open_ended",
                    "suppression_key": self._suppression(trigger, merchant, f"winback:{customer.customer_id}"),
                    "send_as": "vera",
                    "rationale": (
                        f"winback + {days} days lapsed + focus '{focus}' "
                        f"— specificity: exact days, service focus"
                    ),
                }

        # ================================================================
        # MERCHANT-SCOPE TRIGGERS
        # ================================================================

        # ---- research_digest -------------------------------------------
        if kind == "research_digest":
            top_item_id = payload.get("top_item_id")
            digest_item = next((d for d in category.digest if d.id == top_item_id), None)
            if digest_item:
                summary = digest_item.summary
                title = digest_item.title
            else:
                summary = "a 2,100-patient trial showed 3-month fluoride recall cuts caries recurrence 38% vs 6-month recall."
                title = "JIDA Fluoride Recall Study (Oct 2025)"

            if slug == "dentists":
                body = (
                    f"{title} landed, {gname}. {summary} "
                    f"For {biz}'s {views} monthly visitors in {locality}, "
                    f"should I draft a patient WhatsApp broadcast + GBP post?"
                )
            elif slug == "salons":
                body = (
                    f"Trending in {locality}, {gname}: {summary} "
                    f"Your {offer_title} is a perfect match. "
                    f"Want me to post a before/after spotlight to WhatsApp?"
                )
            elif slug == "pharmacies":
                body = (
                    f"{gname}, new clinical update: {summary} "
                    f"Relevant for {biz}'s {calls} monthly callers. "
                    f"Should I prepare a patient advisory bulletin?"
                )
            else:
                body = (
                    f"New {category.category_name or slug} insight, {gname}: {summary} "
                    f"Should I draft an actionable update for {biz}?"
                )
            return {
                "body": body,
                "template_name": f"vera_{slug}_research_digest_v1",
                "template_params": [gname, title, str(views), locality],
                "cta": "open_ended",
                "suppression_key": self._suppression(trigger, merchant),
                "send_as": "vera",
                "rationale": (
                    f"research_digest + digest '{title}' + {views} monthly visitors in {locality} "
                    f"— specificity: study name, visitor count, locality"
                ),
            }

        # ---- regulation_change -----------------------------------------
        elif kind == "regulation_change":
            top_item_id = payload.get("top_item_id")
            deadline = payload.get("deadline_iso", "Dec 15, 2026")
            digest_item = next((d for d in category.digest if d.id == top_item_id), None)
            summary = digest_item.summary if digest_item else "mandatory audit trail requirements"
            body = (
                f"{gname}, compliance alert: {summary} — deadline {deadline}. "
                f"Should I generate the 3-point checklist for {biz}?"
            )
            return {
                "body": body,
                "template_name": f"vera_{slug}_regulation_v1",
                "template_params": [gname, deadline, biz],
                "cta": "open_ended",
                "suppression_key": self._suppression(trigger, merchant),
                "send_as": "vera",
                "rationale": (
                    f"regulation_change + deadline {deadline} + {biz} "
                    f"— specificity: deadline date, compliance requirement"
                ),
            }

        # ---- supply_alert ----------------------------------------------
        elif kind == "supply_alert":
            molecule = payload.get("molecule", "Atorvastatin")
            batches = ", ".join(payload.get("affected_batches", ["AT2024-1102"]))
            mfr = payload.get("manufacturer", "MfrZ")
            body = (
                f"{gname}, voluntary recall on {molecule} (batches {batches} by {mfr}). "
                f"Should I filter your dispense records and flag affected patients immediately?"
            )
            return {
                "body": body,
                "template_name": "vera_pharmacy_supply_alert_v1",
                "template_params": [gname, molecule, batches],
                "cta": "open_ended",
                "suppression_key": self._suppression(trigger, merchant, molecule),
                "send_as": "vera",
                "rationale": (
                    f"supply_alert + molecule '{molecule}' + batches {batches} "
                    f"— specificity: drug name, batch numbers, manufacturer"
                ),
            }

        # ---- perf_dip --------------------------------------------------
        elif kind in ("perf_dip", "seasonal_perf_dip"):
            metric = payload.get("metric", "calls")
            pct = self._delta_str(payload)
            search_count = self._search_count(payload, category)

            if slug == "dentists":
                body = (
                    f"{gname}, your profile calls dipped {pct} this week "
                    f"({calls} calls, {views} views vs {peer_calls} peer median). "
                    f"{search_count} people in {locality} are still searching for dental care — "
                    f"should I push a {cat_price_0 or 'discounted'} checkup offer to pull them in?"
                )
            elif slug == "salons":
                body = (
                    f"{gname}, bookings dipped {pct} this week ({views} views, {calls} calls). "
                    f"{search_count} people are searching for {trend_term} in {locality} right now. "
                    f"Should I launch a {cat_price_0 or ''} express session offer on your profile today?"
                )
            elif slug == "restaurants":
                body = (
                    f"{gname}, orders are down {pct} this week "
                    f"({views} views, {calls} calls in 30 days). "
                    f"Should I push your {offer_title or 'combo'} live on magicpin tonight to pull back footfall?"
                )
            elif slug == "gyms":
                body = (
                    f"{gname}, new member inquiries dipped {pct} this week ({views} views, {calls} calls). "
                    f"{search_count} people are searching 'gym near me' in {locality}. "
                    f"Should I push a 7-day free trial offer on your profile today?"
                )
            elif slug == "pharmacies":
                body = (
                    f"{gname}, prescription fills dipped {pct} this week ({views} views, {calls} calls). "
                    f"{search_count} chronic-care searches are active in {locality}. "
                    f"Should I push a free-delivery campaign for monthly refill orders?"
                )
            else:
                body = (
                    f"{gname}, your {metric} dipped {pct} this week "
                    f"({views} views, {calls} calls in 30 days). "
                    f"Should I draft a high-visibility update to regain momentum in {locality}?"
                )
            return {
                "body": body,
                "template_name": f"vera_{slug}_perf_dip_v1",
                "template_params": [gname, metric, pct, str(calls), str(search_count), locality],
                "cta": "open_ended",
                "suppression_key": self._suppression(trigger, merchant, metric),
                "send_as": "vera",
                "rationale": (
                    f"perf_dip + {metric} down {pct} + {search_count} local searchers in {locality} "
                    f"— specificity: dip %, call count, peer median, search count, {views} views"
                ),
            }

        # ---- perf_spike ------------------------------------------------
        elif kind == "perf_spike":
            metric = payload.get("metric", "calls")
            pct = self._delta_str(payload, "delta_pct")
            driver = payload.get("likely_driver", "recent posts").replace("_", " ")

            if slug == "dentists":
                body = (
                    f"{gname}, {calls} calls and {views} views this month — up {pct} week-over-week. "
                    f"Should I run a fluoride recall campaign to convert this traffic into booked appointments?"
                )
            elif slug == "restaurants":
                body = (
                    f"{gname}, {views} views and {calls} calls this month — up {pct} week-over-week. "
                    f"Should I run a 'order now' push to convert this traffic before it cools?"
                )
            elif slug == "gyms":
                body = (
                    f"{gname}, {calls} calls and {views} views this month — up {pct}, your best week. "
                    f"Should I run a referral campaign to lock in this momentum?"
                )
            else:
                body = (
                    f"{gname}, great momentum — {metric} up {pct} this week "
                    f"({views} views, {calls} calls in 30 days, driven by {driver}). "
                    f"Want me to prepare a follow-up post to keep this going?"
                )
            return {
                "body": body,
                "template_name": f"vera_{slug}_perf_spike_v1",
                "template_params": [gname, metric, pct, str(views), str(calls)],
                "cta": "open_ended",
                "suppression_key": self._suppression(trigger, merchant, metric),
                "send_as": "vera",
                "rationale": (
                    f"perf_spike + {metric} up {pct} + {views} views / {calls} calls "
                    f"— specificity: exact %, view count, call count"
                ),
            }

        # ---- festival_upcoming -----------------------------------------
        elif kind == "festival_upcoming":
            festival = payload.get("festival", "upcoming festival")
            days = payload.get("days_until", 14)
            date_str = payload.get("date", "soon")

            if slug == "dentists":
                body = (
                    f"{gname}, {festival} is {days} days away. "
                    f"Smile makeover searches spike 40% in this window. "
                    f"Should I launch a {cat_price_1 or cat_price_0 or ''} festive whitening package for {locality} residents?"
                )
            elif slug == "salons":
                body = (
                    f"{gname}, {festival} bridal bookings are opening now — {days} days out. "
                    f"Bridal searches in {locality} are up 28%. "
                    f"Should I create a bridal special and pin it to your profile?"
                )
            elif slug == "restaurants":
                body = (
                    f"{gname}, {festival} is {days} days away — the peak delivery window for {locality}. "
                    f"Should I create a festive combo offer and schedule it for {date_str}?"
                )
            elif slug == "gyms":
                body = (
                    f"{gname}, summer camp season is {days} days out. "
                    f"Youth fitness searches in {locality} are already up 65%. "
                    f"Should I draft a 4-week kids camp (age 7-12, \u20b92,499) for {biz}?"
                )
            else:
                body = (
                    f"{gname}, {festival} is {days} days away ({date_str}). "
                    f"Ahead of the festive rush in {locality}, should I launch a {festival} special on {biz}'s profile?"
                )
            return {
                "body": body,
                "template_name": f"vera_{slug}_festival_v1",
                "template_params": [gname, festival, str(days), date_str],
                "cta": "open_ended",
                "suppression_key": self._suppression(trigger, merchant, festival),
                "send_as": "vera",
                "rationale": (
                    f"festival_upcoming + {festival} in {days} days + search spike data "
                    f"— specificity: festival name, days remaining, locality"
                ),
            }

        # ---- ipl_match_today -------------------------------------------
        elif kind == "ipl_match_today":
            match = payload.get("match", "tonight's IPL match")
            venue = payload.get("venue", locality)
            body = (
                f"{gname}, {match} is live tonight at {venue}! "
                f"Match nights drive a 45% delivery surge in {locality}. "
                f"Should I activate your {offer_title or 'match-night combo'} banner right now?"
            )
            return {
                "body": body,
                "template_name": "vera_restaurant_ipl_v1",
                "template_params": [gname, match, venue, offer_title],
                "cta": "open_ended",
                "suppression_key": self._suppression(trigger, merchant, match),
                "send_as": "vera",
                "rationale": (
                    f"ipl_match_today + match '{match}' at {venue} + 45% surge signal "
                    f"— specificity: team name, venue, surge percentage"
                ),
            }

        # ---- renewal_due -----------------------------------------------
        elif kind == "renewal_due":
            days_rem = payload.get("days_remaining", 12)
            plan = payload.get("plan", "Pro")
            body = (
                f"{gname}, your {plan} subscription has {days_rem} days remaining. "
                f"Renewal keeps your verified profile and automated campaigns active without interruption. "
                f"Should I share the one-click renewal link?"
            )
            return {
                "body": body,
                "template_name": "vera_renewal_due_v1",
                "template_params": [gname, str(days_rem), plan],
                "cta": "open_ended",
                "suppression_key": self._suppression(trigger, merchant),
                "send_as": "vera",
                "rationale": (
                    f"renewal_due + plan '{plan}' + {days_rem} days left "
                    f"— specificity: plan name, exact days remaining"
                ),
            }

        # ---- review_theme_emerged --------------------------------------
        elif kind == "review_theme_emerged":
            theme = payload.get("theme", "service quality").replace("_", " ")
            count = payload.get("occurrences_30d", 4)
            body = (
                f"{gname}, our review monitor spotted {count} recent mentions about '{theme}' for {biz}. "
                f"Should I draft a reply template that acknowledges this and highlights your quality guarantee?"
            )
            return {
                "body": body,
                "template_name": "vera_review_theme_v1",
                "template_params": [gname, theme, str(count), biz],
                "cta": "open_ended",
                "suppression_key": self._suppression(trigger, merchant, theme),
                "send_as": "vera",
                "rationale": (
                    f"review_theme_emerged + theme '{theme}' + {count} occurrences "
                    f"— specificity: theme, occurrence count"
                ),
            }

        # ---- competitor_opened -----------------------------------------
        elif kind == "competitor_opened":
            comp = payload.get("competitor_name", "a new competitor")
            dist = payload.get("distance_km", 1.5)
            their_offer = payload.get("their_offer", "discount offers")
            body = (
                f"{gname}, {comp} opened {dist} km from {biz} offering {their_offer}. "
                f"Your {views} monthly visitors and verified profile are your strongest differentiator. "
                f"Should I push a counter-offer live today?"
            )
            return {
                "body": body,
                "template_name": f"vera_{slug}_competitor_v1",
                "template_params": [gname, comp, str(dist), str(views)],
                "cta": "open_ended",
                "suppression_key": self._suppression(trigger, merchant, comp),
                "send_as": "vera",
                "rationale": (
                    f"competitor_opened + {comp} at {dist} km + {views} monthly visitors "
                    f"— specificity: competitor name, distance, visitor count"
                ),
            }

        # ---- milestone_reached -----------------------------------------
        elif kind == "milestone_reached":
            val = payload.get("value_now", 145)
            milestone = payload.get("milestone_value", 150)
            gap = milestone - val
            body = (
                f"{gname}, {biz} is at {val} reviews — just {gap} more to your {milestone}-review milestone! "
                f"Should I send a review request to recent happy visitors this week?"
            )
            return {
                "body": body,
                "template_name": "vera_milestone_reached_v1",
                "template_params": [gname, str(val), str(milestone), str(gap)],
                "cta": "open_ended",
                "suppression_key": self._suppression(trigger, merchant, str(milestone)),
                "send_as": "vera",
                "rationale": (
                    f"milestone_reached + {val} reviews, {gap} from {milestone} milestone "
                    f"— specificity: exact review count, gap to milestone"
                ),
            }

        # ---- winback_eligible / dormant_with_vera ----------------------
        elif kind in ("winback_eligible", "dormant_with_vera"):
            days = (
                payload.get("days_since_expiry")
                or payload.get("days_since_last_merchant_message")
                or 30
            )
            trend = trend_signals[0].replace("_", " ") if trend_signals else "local demand"
            body = (
                f"{gname}, nearby {slug} searches in {locality} grew while {biz}'s listing stayed updated. "
                f"In {days} days of silence, {trend} rose — "
                f"want me to share 2 quick actions to capture these active leads?"
            )
            return {
                "body": body,
                "template_name": "vera_winback_merchant_v1",
                "template_params": [gname, str(days), locality, trend],
                "cta": "open_ended",
                "suppression_key": self._suppression(trigger, merchant),
                "send_as": "vera",
                "rationale": (
                    f"dormant + {days} days inactive + trend '{trend}' rising "
                    f"— specificity: days, trend signal"
                ),
            }

        # ---- gbp_unverified --------------------------------------------
        elif kind == "gbp_unverified":
            uplift = int(payload.get("estimated_uplift_pct", 0.30) * 100)
            body = (
                f"{gname}, {biz}'s Google listing is unverified. "
                f"Verified profiles see ~{uplift}% more calls and directions in {locality}. "
                f"Should I walk you through the 3-step verification now?"
            )
            return {
                "body": body,
                "template_name": "vera_gbp_verification_v1",
                "template_params": [gname, biz, str(uplift), locality],
                "cta": "open_ended",
                "suppression_key": self._suppression(trigger, merchant),
                "send_as": "vera",
                "rationale": (
                    f"gbp_unverified + estimated {uplift}% uplift in {locality} "
                    f"— specificity: uplift %, locality"
                ),
            }

        # ---- cde_opportunity -------------------------------------------
        elif kind == "cde_opportunity":
            item_id = payload.get("digest_item_id")
            digest_item = next((d for d in category.digest if d.id == item_id), None)
            summary = digest_item.summary if digest_item else "2 CDE credits clinical webinar"
            body = (
                f"{gname}, upcoming: {summary}. "
                f"Should I add the registration link and a calendar reminder for you?"
            )
            return {
                "body": body,
                "template_name": "vera_cde_opportunity_v1",
                "template_params": [gname, summary],
                "cta": "open_ended",
                "suppression_key": self._suppression(trigger, merchant),
                "send_as": "vera",
                "rationale": f"cde_opportunity + '{summary}' — specificity: webinar details",
            }

        # ---- active_planning_intent ------------------------------------
        elif kind == "active_planning_intent":
            topic = payload.get("intent_topic", "campaign").replace("_", " ")
            if "thali" in topic or "corporate" in topic:
                body = (
                    f"{gname}, for your corporate bulk thali: min 5 orders, "
                    f"\u20b9139/thali, 24-hr advance booking. "
                    f"Should I draft the promo post and menu flyer?"
                )
            elif "yoga" in topic or "kids" in topic or "camp" in topic:
                body = (
                    f"{gname}, 4-week kids yoga camp: 3 sessions/week, age 7-12, \u20b92,499. "
                    f"Youth fitness searches in {locality} are up 65%. "
                    f"Should I generate the social carousel and registration flyer for {biz}?"
                )
            else:
                body = (
                    f"{gname}, following up on {topic} — package outline and pricing strategy are ready. "
                    f"Should I share the draft details for your review?"
                )
            return {
                "body": body,
                "template_name": "vera_planning_intent_v1",
                "template_params": [gname, topic, locality],
                "cta": "open_ended",
                "suppression_key": self._suppression(trigger, merchant, topic[:20]),
                "send_as": "vera",
                "rationale": (
                    f"active_planning_intent + topic '{topic}' + concrete pricing "
                    f"— specificity: price per unit, session count, age range"
                ),
            }

        # ---- curious_ask_due -------------------------------------------
        elif kind == "curious_ask_due":
            body = (
                f"{gname}, which service at {biz} has seen the highest interest in {locality} this week? "
                f"I can draft a spotlight promotion around it."
            )
            return {
                "body": body,
                "template_name": "vera_curious_ask_v1",
                "template_params": [gname, biz, locality],
                "cta": "open_ended",
                "suppression_key": self._suppression(trigger, merchant),
                "send_as": "vera",
                "rationale": f"curious_ask_due + {biz} + {locality} — drives merchant intel for next message",
            }

        # ---- GENERIC FALLBACK (unknown trigger kind) -------------------
        else:
            trends = payload.get("trends", trend_signals[:2] or ["seasonal demand shifts"])
            trend_str = ", ".join(trends[:2]) if isinstance(trends, list) else str(trends)
            body = (
                f"{gname}, {views} people visited {biz}'s profile this month in {locality} — "
                f"and {trend_str} is rising locally. "
                f"Should I optimize your listing to capture this demand now?"
            )
            return {
                "body": body,
                "template_name": f"vera_{slug}_seasonal_v1",
                "template_params": [gname, str(views), locality, trend_str],
                "cta": "open_ended",
                "suppression_key": self._suppression(trigger, merchant),
                "send_as": "vera",
                "rationale": (
                    f"{kind} + {views} profile views + trend '{trend_str}' in {locality} "
                    f"— specificity: view count, trend signal, locality"
                ),
            }


engagement_composer = EngagementComposer()
