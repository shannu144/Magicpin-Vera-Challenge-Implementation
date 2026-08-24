from __future__ import annotations

import re
from typing import Tuple


class IntentDetector:
    """
    Classifies user/merchant incoming responses into actionable intents.
    """

    # Intent categories
    INTENT_ACTION_JOIN = "join"
    INTENT_YES = "yes"
    INTENT_NO = "no"
    INTENT_NOT_INTERESTED = "not_interested"
    INTENT_STOP = "stop"
    INTENT_TELL_ME_MORE = "tell_me_more"
    INTENT_SEND_DETAILS = "send_details"
    INTENT_HOW_IT_WORKS = "how_does_this_work"
    INTENT_PRICE_QUESTION = "price_question"
    INTENT_BUSY_LATER = "busy_later"
    INTENT_AUTO_REPLY = "auto_reply"
    INTENT_OFF_TOPIC = "off_topic"
    INTENT_AMBIGUOUS = "ambiguous"

    AUTO_REPLY_PATTERNS = [
        r"thank you for (contacting|messaging|reaching)",
        r"we are currently (closed|away|unavailable|busy)",
        r"out of office",
        r"this is an automated (message|response|reply)",
        r"we will get back to you",
        r"auto(-|\s)?reply",
        r"will respond shortly",
        r"for urgent inquiries please call",
        r"press 1 for",
    ]

    ACTION_JOIN_PATTERNS = [
        r"\b(let'?s\s+do\s+it|lets\s+do\s+it)\b",
        r"\b(i\s+want\s+to\s+join|sign\s+me\s+up|join\s+now|count\s+me\s+in)\b",
        r"\b(let'?s\s+proceed|proceed\s+with\s+it|start\s+it|go\s+ahead|do\s+it)\b",
        r"\b(activate\s+this|setup\s+now|set\s+it\s+up)\b",
        r"\b(send\s+me\s+the\s+list\s+please|yes\s+send\s+me\s+the\s+list)\b",
        r"\b(yes\s+please,?\s+focus\s+on)\b",
        r"\b(book\s+this\s+slot|confirm\s+slot|schedule\s+it)\b",
    ]

    NO_STOP_PATTERNS = [
        r"\b(stop|unsubscribe|cancel|opt\s*out|remove\s+me)\b",
        r"\b(not\s+interested|no\s+thanks|don'?t\s+message|leave\s+me\s+alone|never\s+again)\b",
        r"\b(don'?t\s+need|no\s+need|no\b)",
    ]

    PRICE_PATTERNS = [
        r"\b(how\s+much|what\s+is\s+the\s+price|pricing|cost|charges|fee|rates?|how\s+expensive)\b",
        r"\b(what\s+does\s+it\s+cost|is\s+it\s+free|any\s+discount)\b",
    ]

    TELL_ME_MORE_PATTERNS = [
        r"\b(tell\s+me\s+more|share\s+more|more\s+details?|explain\s+more)\b",
        r"\b(send\s+details|send\s+the\s+abstract|pull\s+the\s+abstract|share\s+the\s+abstract)\b",
        r"\b(how\s+does\s+this\s+work|what\s+would\s+it\s+look\s+like|what\s+are\s+the\s+steps)\b",
        r"\b(what\s+do\s+you\s+mean|can\s+you\s+elaborate)\b",
    ]

    BUSY_LATER_PATTERNS = [
        r"\b(busy\s+right\s+now|call\s+me\s+later|message\s+me\s+later|later|not\s+now)\b",
        r"\b(ping\s+me\s+tomorrow|after\s+some\s+time|in\s+a\s+meeting)\b",
    ]

    OFF_TOPIC_PATTERNS = [
        r"\b(gst|tax|income\s+tax|file\s+my\s+return|itr)\b",
        r"\b(weather|cricket\s+score|movie|joke|recipe|who\s+are\s+you\s+really)\b",
        r"\b(loan|credit\s+card|crypto|bitcoin|forex)\b",
    ]

    YES_PATTERNS = [
        r"\b(yes|yeah|yep|yup|sure|ok|okay|sounds\s+good|definitely|absolutely|fine|why\s+not)\b",
        r"\b(interested|ha|haan|theek\s+hai|sahi\s+hai)\b",
    ]

    def detect(self, message: str) -> Tuple[str, float]:
        """
        Detects intent from message string.
        Returns (intent, confidence)
        """
        msg = message.strip().lower()

        # Check auto-reply first
        for pat in self.AUTO_REPLY_PATTERNS:
            if re.search(pat, msg, re.IGNORECASE):
                return self.INTENT_AUTO_REPLY, 0.95

        # Check action join / clear commitment (highest priority for replay scenarios)
        for pat in self.ACTION_JOIN_PATTERNS:
            if re.search(pat, msg, re.IGNORECASE):
                return self.INTENT_ACTION_JOIN, 0.95

        # Check No / Stop / Unsubscribe
        for pat in self.NO_STOP_PATTERNS:
            if re.search(pat, msg, re.IGNORECASE):
                if re.search(r"\b(stop|unsubscribe|opt\s*out)\b", msg):
                    return self.INTENT_STOP, 0.95
                return self.INTENT_NOT_INTERESTED, 0.90

        # Check Off-topic / Hostile / Unrelated
        for pat in self.OFF_TOPIC_PATTERNS:
            if re.search(pat, msg, re.IGNORECASE):
                return self.INTENT_OFF_TOPIC, 0.90

        # Check Price question
        for pat in self.PRICE_PATTERNS:
            if re.search(pat, msg, re.IGNORECASE):
                return self.INTENT_PRICE_QUESTION, 0.90

        # Check Tell me more / Send details
        for pat in self.TELL_ME_MORE_PATTERNS:
            if re.search(pat, msg, re.IGNORECASE):
                if "how" in msg and "work" in msg:
                    return self.INTENT_HOW_IT_WORKS, 0.90
                if "detail" in msg or "abstract" in msg:
                    return self.INTENT_SEND_DETAILS, 0.90
                return self.INTENT_TELL_ME_MORE, 0.90

        # Check Busy / Later
        for pat in self.BUSY_LATER_PATTERNS:
            if re.search(pat, msg, re.IGNORECASE):
                return self.INTENT_BUSY_LATER, 0.90

        # Check General Yes / Interested
        for pat in self.YES_PATTERNS:
            if re.search(pat, msg, re.IGNORECASE):
                return self.INTENT_YES, 0.85

        return self.INTENT_AMBIGUOUS, 0.50


intent_detector = IntentDetector()
