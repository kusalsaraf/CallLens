"""Structured demo call scenarios for seeding realistic analytics.

Each scenario defines a two-speaker call script, target topic(s), agent/team
assignment, and notes about its expected scoring behavior. The set is designed
to produce a realistic spread across quality bands, compliance outcomes, and
topic categories.
"""

from __future__ import annotations

from typing import TypedDict


class Turn(TypedDict):
    """A single speaker turn in a call script."""

    speaker: str  # "agent" or "customer"
    text: str


class Scenario(TypedDict):
    """A complete demo call scenario."""

    id: str
    title: str
    topics: list[str]  # topic slugs
    agent: str
    team: str
    turns: list[Turn]
    notes: str


AGENTS: dict[str, str] = {
    "Sarah Chen": "Collections East",
    "Marcus Rivera": "Collections East",
    "Priya Patel": "Support West",
    "James O'Brien": "Support West",
    "Aisha Johnson": "Collections East",
}

TEAMS: list[str] = ["Collections East", "Support West"]

SCENARIOS: list[Scenario] = [
    # ── 1. HIGH-QUALITY: billing dispute resolved ─────────────────────
    {
        "id": "demo-billing-good",
        "title": "Billing dispute — resolved cleanly",
        "topics": ["billing_dispute"],
        "agent": "Sarah Chen",
        "team": "Collections East",
        "turns": [
            {
                "speaker": "agent",
                "text": "Thank you for calling support, this is Sarah. How can I help you today?",
            },
            {
                "speaker": "customer",
                "text": "Hi, I noticed an extra charge of $49.99 on my statement from last month. I didn't authorize that.",
            },
            {
                "speaker": "agent",
                "text": "I understand your concern about that unexpected charge. Let me pull up your account and look into this right away.",
            },
            {
                "speaker": "customer",
                "text": "My email is john.doe@example.com and my phone is 555-0142.",
            },
            {
                "speaker": "agent",
                "text": "Thank you, I can see the charge here. It appears to be a duplicate billing from our system. I apologize for the inconvenience — this was clearly an error on our end.",
            },
            {"speaker": "customer", "text": "Okay, so can you reverse it?"},
            {
                "speaker": "agent",
                "text": "Absolutely. I've initiated a refund of $49.99 which should appear on your next statement. I apologize again for the trouble.",
            },
            {"speaker": "customer", "text": "Great, that's all I needed."},
            {
                "speaker": "agent",
                "text": "I'm glad I could help. Is there anything else I can assist you with today?",
            },
            {"speaker": "customer", "text": "No, that's it. Thanks!"},
            {"speaker": "agent", "text": "Thank you for calling. Have a wonderful day!"},
        ],
        "notes": "Clean high-scoring call. All compliance phrases present (I understand, I apologize, Is there anything else). Contains synthetic PII (email, phone).",
    },
    # ── 2. AT-RISK: cancellation narrowly saved ──────────────────────
    {
        "id": "demo-cancel-atrisk",
        "title": "Cancellation attempt — narrowly saved",
        "topics": ["cancellation_churn_risk", "retention_save"],
        "agent": "Marcus Rivera",
        "team": "Collections East",
        "turns": [
            {"speaker": "agent", "text": "Collections East, Marcus speaking. How can I help?"},
            {
                "speaker": "customer",
                "text": "I want to cancel my account immediately. I've been charged twice this month and nobody seems to care.",
            },
            {
                "speaker": "agent",
                "text": "I can see why that would be frustrating. Let me look into the double charge for you.",
            },
            {
                "speaker": "customer",
                "text": "I've called three times already. My card ending in 4111 1111 1111 1111 keeps getting hit.",
            },
            {
                "speaker": "agent",
                "text": "I understand. I can see the duplicate charge here. Before we proceed with cancellation, would you consider staying if I refund both charges and apply a 20% loyalty discount for the next three months?",
            },
            {
                "speaker": "customer",
                "text": "Hmm. That's a decent offer. Fine, I'll stay for now but if this happens again I'm done.",
            },
            {
                "speaker": "agent",
                "text": "Completely fair. I've processed the refund and the discount is active. Is there anything else?",
            },
            {"speaker": "customer", "text": "No, that's it."},
        ],
        "notes": "At-risk band. Retention save but shaky. Contains Luhn-valid card number (4111...). Missing 'I apologize'.",
    },
    # ── 3. FAIL: compliance violation, escalation ────────────────────
    {
        "id": "demo-compliance-fail",
        "title": "Compliance failure — escalation triggered",
        "topics": ["complaint_escalation", "billing_dispute"],
        "agent": "James O'Brien",
        "team": "Support West",
        "turns": [
            {"speaker": "agent", "text": "Support line, James here."},
            {
                "speaker": "customer",
                "text": "I've been overcharged $200 and your company is stealing from me. I want to speak to a manager RIGHT NOW.",
            },
            {
                "speaker": "agent",
                "text": "Look, I can see your account. The charges are correct based on your plan.",
            },
            {
                "speaker": "customer",
                "text": "They are NOT correct! I downgraded last month and you're still charging the old rate. This is fraud!",
            },
            {
                "speaker": "agent",
                "text": "That's just how the billing cycle works. The change takes effect next month.",
            },
            {
                "speaker": "customer",
                "text": "That's unacceptable! Get me your supervisor. I'm filing a complaint with the BBB.",
            },
            {"speaker": "agent", "text": "Fine, I'll transfer you. Hold on."},
        ],
        "notes": "Fail band. No empathy, no compliance phrases, dismissive tone. Should trigger escalate_for_review.",
    },
    # ── 4. HIGH-QUALITY: technical issue resolved ────────────────────
    {
        "id": "demo-tech-good",
        "title": "Technical issue — expert resolution",
        "topics": ["technical_issue"],
        "agent": "Priya Patel",
        "team": "Support West",
        "turns": [
            {"speaker": "agent", "text": "Support West, this is Priya. How can I help you today?"},
            {
                "speaker": "customer",
                "text": "My dashboard has been showing an error for the past two hours. Error code 5032.",
            },
            {
                "speaker": "agent",
                "text": "I understand how frustrating that must be. Error 5032 is related to our API gateway. Let me check the system status.",
            },
            {"speaker": "customer", "text": "Is it a known issue?"},
            {
                "speaker": "agent",
                "text": "Yes, I can see our engineering team deployed a fix about 30 minutes ago. Could you try clearing your browser cache and refreshing?",
            },
            {"speaker": "customer", "text": "Let me try... yes, it's working now! That fixed it."},
            {
                "speaker": "agent",
                "text": "I apologize for the disruption. I'll note your account so if it recurs, our team can prioritize your case.",
            },
            {"speaker": "customer", "text": "Thanks, that's great."},
            {"speaker": "agent", "text": "You're welcome. Is there anything else I can help with?"},
            {"speaker": "customer", "text": "No, that's all."},
            {"speaker": "agent", "text": "Have a great day!"},
        ],
        "notes": "High-scoring technical resolution. All compliance phrases present.",
    },
    # ── 5. AT-RISK: refund dispute, partial resolution ───────────────
    {
        "id": "demo-refund-atrisk",
        "title": "Refund request — partial resolution",
        "topics": ["refund_request", "billing_dispute"],
        "agent": "Sarah Chen",
        "team": "Collections East",
        "turns": [
            {"speaker": "agent", "text": "Thank you for calling, this is Sarah. How can I help?"},
            {
                "speaker": "customer",
                "text": "I need a full refund for the premium plan. I signed up two weeks ago and it's nothing like what was advertised.",
            },
            {
                "speaker": "agent",
                "text": "I understand your frustration. Can you tell me specifically what features aren't meeting your expectations?",
            },
            {
                "speaker": "customer",
                "text": "The reporting dashboard is completely different from the demo your sales team showed me. My email is jane.smith@testmail.com if you need to look up my account.",
            },
            {
                "speaker": "agent",
                "text": "I see your account. Our refund policy allows a partial refund within 30 days. I can process a 50% refund and extend your trial for an additional month.",
            },
            {"speaker": "customer", "text": "That's not ideal but I guess I'll take it for now."},
            {
                "speaker": "agent",
                "text": "I apologize for the experience not matching expectations. I've processed the partial refund. Is there anything else?",
            },
            {"speaker": "customer", "text": "No, that's fine."},
        ],
        "notes": "At-risk band. Partial resolution only. Contains email PII.",
    },
    # ── 6. FAIL: payment arrangement badly handled ───────────────────
    {
        "id": "demo-payment-fail",
        "title": "Payment arrangement — poorly handled",
        "topics": ["payment_arrangement"],
        "agent": "Marcus Rivera",
        "team": "Collections East",
        "turns": [
            {"speaker": "agent", "text": "Collections, Marcus."},
            {
                "speaker": "customer",
                "text": "Hi, I lost my job last month and I can't pay the full balance. Can we set up a payment plan?",
            },
            {
                "speaker": "agent",
                "text": "Your balance is $1,247. We need at least 50% upfront for a payment plan.",
            },
            {
                "speaker": "customer",
                "text": "I literally just told you I can't afford it. Can't you do something more flexible? My SSN on file is 123-45-6789.",
            },
            {
                "speaker": "agent",
                "text": "Those are the rules. If you can't pay, the account goes to collections in 30 days.",
            },
            {
                "speaker": "customer",
                "text": "This is ridiculous. You're not even trying to help me.",
            },
            {
                "speaker": "agent",
                "text": "I'm just telling you the policy. Do you want to make a payment or not?",
            },
        ],
        "notes": "Fail band. Zero empathy, rigid policy enforcement, no compliance phrases. Contains SSN PII. Should trigger escalation.",
    },
    # ── 7. HIGH-QUALITY: account access restored ─────────────────────
    {
        "id": "demo-access-good",
        "title": "Account access — quick restore",
        "topics": ["account_access"],
        "agent": "Aisha Johnson",
        "team": "Collections East",
        "turns": [
            {
                "speaker": "agent",
                "text": "Thank you for calling support, this is Aisha. How can I assist you today?",
            },
            {
                "speaker": "customer",
                "text": "I've been locked out of my account for two days. I've tried resetting my password but the email never arrives.",
            },
            {
                "speaker": "agent",
                "text": "I understand how frustrating that must be. Let me verify your identity and get you back in right away. Can you confirm the email on file?",
            },
            {"speaker": "customer", "text": "It should be mike.wilson@fakeemail.org."},
            {
                "speaker": "agent",
                "text": "I see the issue — your recovery email had a typo. I've corrected it and sent a fresh password reset link. You should receive it within a minute.",
            },
            {"speaker": "customer", "text": "Just got it! And I'm in. Thank you so much."},
            {
                "speaker": "agent",
                "text": "Wonderful! I apologize for the inconvenience with the locked account. Is there anything else I can help you with?",
            },
            {"speaker": "customer", "text": "Nope, you've been amazing. Thanks!"},
        ],
        "notes": "High-scoring call. Quick resolution, empathy, all compliance phrases. Contains email PII.",
    },
    # ── 8. AT-RISK: product question with upsell ─────────────────────
    {
        "id": "demo-product-atrisk",
        "title": "Product question — upgrade discussion",
        "topics": ["product_question"],
        "agent": "Priya Patel",
        "team": "Support West",
        "turns": [
            {"speaker": "agent", "text": "Support West, Priya here. What can I help with?"},
            {
                "speaker": "customer",
                "text": "I'm trying to figure out the difference between the Pro and Enterprise plans. The website isn't very clear.",
            },
            {
                "speaker": "agent",
                "text": "Great question. The main differences are the number of users and the analytics depth. Pro supports up to 10 users with basic analytics, while Enterprise has unlimited users with advanced reporting.",
            },
            {
                "speaker": "customer",
                "text": "We have 15 people. So we'd need Enterprise? That's a big price jump.",
            },
            {
                "speaker": "agent",
                "text": "I understand the concern about pricing. We do have a mid-tier option that supports up to 25 users at a lower price point. Would you like me to send you a comparison?",
            },
            {"speaker": "customer", "text": "Yes, send it to team@ourcompany.com please."},
            {"speaker": "agent", "text": "Done. Is there anything else?"},
            {"speaker": "customer", "text": "No, that covers it."},
        ],
        "notes": "At-risk band. Helpful but missing 'I apologize'. Contains email PII.",
    },
    # ── 9. HIGH-QUALITY: delivery tracking ───────────────────────────
    {
        "id": "demo-delivery-good",
        "title": "Delivery issue — tracked and resolved",
        "topics": ["delivery_shipping"],
        "agent": "James O'Brien",
        "team": "Support West",
        "turns": [
            {
                "speaker": "agent",
                "text": "Thank you for calling support, James here. How can I help today?",
            },
            {
                "speaker": "customer",
                "text": "My package was supposed to arrive three days ago and the tracking shows it's stuck in transit.",
            },
            {
                "speaker": "agent",
                "text": "I understand how concerning that is. Let me look up your tracking number and see what's happening.",
            },
            {"speaker": "customer", "text": "The order number is 9847362."},
            {
                "speaker": "agent",
                "text": "I see it. There was a weather delay at the regional hub. The good news is it's now back in transit and should arrive tomorrow. I apologize for the delay.",
            },
            {"speaker": "customer", "text": "Okay, as long as it's actually coming."},
            {
                "speaker": "agent",
                "text": "Absolutely. I've also added priority handling to ensure it's on the first truck tomorrow. Is there anything else I can assist you with?",
            },
            {"speaker": "customer", "text": "No, that's good. Thanks for the help."},
        ],
        "notes": "High-scoring call. Good empathy and compliance. James redeems from scenario 3.",
    },
    # ── 10. FAIL: angry customer, no resolution ──────────────────────
    {
        "id": "demo-churn-fail",
        "title": "Churn call — customer lost",
        "topics": ["cancellation_churn_risk"],
        "agent": "Aisha Johnson",
        "team": "Collections East",
        "turns": [
            {"speaker": "agent", "text": "Collections East, Aisha speaking."},
            {
                "speaker": "customer",
                "text": "Cancel everything. I'm done. Your service has been unreliable for months.",
            },
            {"speaker": "agent", "text": "I can process that for you. Can I ask what happened?"},
            {
                "speaker": "customer",
                "text": "Three outages in two months, and every time I call I get put on hold for 45 minutes. My phone number is 555-0199, just cancel it.",
            },
            {
                "speaker": "agent",
                "text": "I've submitted the cancellation request. You'll receive a confirmation email within 24 hours.",
            },
            {"speaker": "customer", "text": "Finally. Goodbye."},
        ],
        "notes": "Fail band. No retention attempt, no empathy phrases. Contains phone PII. Aisha has mixed results across calls.",
    },
    # ── 11. HIGH-QUALITY: complaint turned positive ──────────────────
    {
        "id": "demo-complaint-good",
        "title": "Complaint escalation — de-escalated well",
        "topics": ["complaint_escalation"],
        "agent": "Sarah Chen",
        "team": "Collections East",
        "turns": [
            {
                "speaker": "agent",
                "text": "Thank you for calling, this is Sarah. How can I help you today?",
            },
            {
                "speaker": "customer",
                "text": "I want to file a formal complaint. Your technician came to my house and left a mess, damaged my wall, and didn't even fix the issue.",
            },
            {
                "speaker": "agent",
                "text": "I understand how upsetting that must be, and I apologize sincerely for that experience. That is absolutely not the level of service we aim for.",
            },
            {
                "speaker": "customer",
                "text": "You bet it's not. I want compensation and I want the repair done properly.",
            },
            {
                "speaker": "agent",
                "text": "Absolutely. I'm creating a priority service ticket right now with full documentation of the damage. I'll also credit your account for this month's service fee. A senior technician will contact you within 24 hours to schedule the repair.",
            },
            {
                "speaker": "customer",
                "text": "Okay, that's more like it. Thank you for actually taking this seriously.",
            },
            {
                "speaker": "agent",
                "text": "You're welcome. I understand your frustration and I want to make sure we make this right. Is there anything else I can help with?",
            },
            {
                "speaker": "customer",
                "text": "No, just make sure someone actually follows up this time.",
            },
            {
                "speaker": "agent",
                "text": "I will personally follow up tomorrow to confirm the scheduling. Thank you for your patience.",
            },
        ],
        "notes": "High-scoring complaint handling. Excellent de-escalation, all compliance phrases.",
    },
    # ── 12. AT-RISK: retention offer, lukewarm ───────────────────────
    {
        "id": "demo-retention-atrisk",
        "title": "Retention attempt — partial success",
        "topics": ["retention_save", "cancellation_churn_risk"],
        "agent": "Marcus Rivera",
        "team": "Collections East",
        "turns": [
            {"speaker": "agent", "text": "Collections, Marcus here. What can I do for you?"},
            {
                "speaker": "customer",
                "text": "I'm thinking about canceling. My bill keeps going up every quarter and I'm not seeing the value.",
            },
            {
                "speaker": "agent",
                "text": "I understand the concern about the pricing trend. Looking at your account, you're on our legacy plan. I can switch you to our current plan which is actually $15 less per month.",
            },
            {
                "speaker": "customer",
                "text": "Why wasn't I told about this before? How long have I been overpaying?",
            },
            {
                "speaker": "agent",
                "text": "I understand that's frustrating. I can apply the new rate going forward. Unfortunately I can't backdate it, but I can add a one-time $50 credit.",
            },
            {"speaker": "customer", "text": "Fine. Switch me over."},
            {"speaker": "agent", "text": "Done. Is there anything else?"},
            {"speaker": "customer", "text": "No."},
        ],
        "notes": "At-risk band. Decent handling but missed 'I apologize'. Customer still unhappy.",
    },
    # ── 13. FAIL: technical call, completely unhelpful ────────────────
    {
        "id": "demo-tech-fail",
        "title": "Technical issue — no resolution",
        "topics": ["technical_issue", "complaint_escalation"],
        "agent": "Priya Patel",
        "team": "Support West",
        "turns": [
            {"speaker": "agent", "text": "Support, Priya."},
            {
                "speaker": "customer",
                "text": "Your app has crashed four times today. I've lost unsaved work each time. This is costing me money.",
            },
            {"speaker": "agent", "text": "Have you tried restarting your device?"},
            {
                "speaker": "customer",
                "text": "Of course I have. Multiple times. The app is broken, not my device.",
            },
            {
                "speaker": "agent",
                "text": "We're aware of some issues. There should be an update coming but I don't have a timeline.",
            },
            {
                "speaker": "customer",
                "text": "That's completely unacceptable. I need this fixed NOW or I need a refund.",
            },
            {
                "speaker": "agent",
                "text": "I can't process refunds from this department. You'd need to call the billing team.",
            },
        ],
        "notes": "Fail band. Dismissive, no empathy, no compliance phrases, dead-end referral. Even good agents have bad calls — Priya is otherwise strong.",
    },
    # ── 14. HIGH-QUALITY: account access with PII ────────────────────
    {
        "id": "demo-access-pii",
        "title": "Account verification with sensitive data",
        "topics": ["account_access"],
        "agent": "James O'Brien",
        "team": "Support West",
        "turns": [
            {
                "speaker": "agent",
                "text": "Thank you for calling, this is James. How can I help you today?",
            },
            {
                "speaker": "customer",
                "text": "I need to update the credit card on my account. The current one expired.",
            },
            {
                "speaker": "agent",
                "text": "I understand. For security, I'll need to verify your identity first. Can you confirm your email address?",
            },
            {
                "speaker": "customer",
                "text": "Sure, it's lisa.martinez@fakemail.net. And my phone is 555-0177.",
            },
            {
                "speaker": "agent",
                "text": "Verified. I can see your account. Please go ahead with the new card number when you're ready.",
            },
            {"speaker": "customer", "text": "It's 5500 0000 0000 0004, expiry 12/27."},
            {
                "speaker": "agent",
                "text": "I've updated the card on file. I apologize for any interruption to your service while the old card was expired. Is there anything else I can assist you with?",
            },
            {"speaker": "customer", "text": "No, that's perfect. Thank you!"},
        ],
        "notes": "High-scoring. Contains multiple PII types: email, phone, Luhn-valid Mastercard test number. All compliance phrases.",
    },
    # ── 15. AT-RISK: delivery complaint, middling ────────────────────
    {
        "id": "demo-delivery-atrisk",
        "title": "Delivery complaint — tracking confusion",
        "topics": ["delivery_shipping"],
        "agent": "Aisha Johnson",
        "team": "Collections East",
        "turns": [
            {"speaker": "agent", "text": "Collections East, Aisha. How can I help?"},
            {
                "speaker": "customer",
                "text": "My order says delivered but I never received it. This is the second time this has happened.",
            },
            {
                "speaker": "agent",
                "text": "I understand that's frustrating. Let me check the delivery details. Can you give me your order number?",
            },
            {
                "speaker": "customer",
                "text": "It's order 7729341. The address is 192.168.1.100... wait, that's my router. I mean 742 Maple Drive.",
            },
            {
                "speaker": "agent",
                "text": "I see the tracking. It shows delivered to the front porch. Sometimes carriers mark it delivered prematurely. I'd suggest checking with neighbors.",
            },
            {"speaker": "customer", "text": "I already did that. Nobody has it."},
            {
                "speaker": "agent",
                "text": "Let me file a delivery investigation. We'll either locate the package or send a replacement within 5 business days. Is there anything else?",
            },
            {"speaker": "customer", "text": "No, just get me my stuff."},
        ],
        "notes": "At-risk band. Adequate but not empathetic enough. Missing 'I apologize'. Contains IP address as accidental PII.",
    },
    # ── 16. HIGH-QUALITY: product upgrade smooth ─────────────────────
    {
        "id": "demo-upgrade-good",
        "title": "Product upgrade — smooth upsell",
        "topics": ["product_question"],
        "agent": "Sarah Chen",
        "team": "Collections East",
        "turns": [
            {
                "speaker": "agent",
                "text": "Thank you for calling, this is Sarah. How can I help you today?",
            },
            {
                "speaker": "customer",
                "text": "I'm interested in upgrading to the business plan. Can you walk me through the features?",
            },
            {
                "speaker": "agent",
                "text": "I'd be happy to! I understand you want to make sure it's the right fit. The business plan includes priority support, advanced analytics, and API access. What features matter most to you?",
            },
            {
                "speaker": "customer",
                "text": "The API access is the big one. We want to integrate with our CRM.",
            },
            {
                "speaker": "agent",
                "text": "Perfect — our API supports full CRM integration with Salesforce, HubSpot, and custom webhooks. I can activate the upgrade right now and send documentation to your email.",
            },
            {"speaker": "customer", "text": "Let's do it. Send it to dev@ourstartup.io."},
            {
                "speaker": "agent",
                "text": "Done! The upgrade is active immediately. I apologize that we didn't reach out sooner about these features — it sounds like they'd have been useful earlier. Is there anything else?",
            },
            {"speaker": "customer", "text": "No, this is great. Thank you!"},
        ],
        "notes": "High-scoring upsell. Natural compliance phrases, good listening.",
    },
]
