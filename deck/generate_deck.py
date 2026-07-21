"""Generates the pitch deck. Run: python deck/generate_deck.py
Requires docs/architecture.png to be present first (rendered from architecture.mmd).
"""
from pptx import Presentation
from pptx.util import Inches, Pt


def add_title_slide(prs, title, subtitle):
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = title
    slide.placeholders[1].text = subtitle
    return slide


def add_bullet_slide(prs, title, bullets):
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = title
    body = slide.placeholders[1].text_frame
    body.clear()
    for i, b in enumerate(bullets):
        p = body.paragraphs[0] if i == 0 else body.add_paragraph()
        p.text = b
        p.font.size = Pt(20)
    return slide


def add_image_slide(prs, title, image_path):
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = title
    slide.shapes.add_picture(image_path, Inches(0.5), Inches(1.5), width=Inches(9))
    return slide


def main():
    prs = Presentation()
    add_title_slide(prs, "Governance Layer for Financial Agents",
                     "The safety layer every other AmEx agent theme needs before deployment")
    add_bullet_slide(prs, "The Problem", [
        "2026: an autonomous airline booking agent misrouted 1,000+ passengers",
        "nothing checked its actions before it executed them",
        "the same failure mode applies to card & payments agents",
    ])
    add_bullet_slide(prs, "Why This Theme", [
        "not a 7th agent competing with the other 6 themes",
        "it's the control plane the other 6 need to be deployable at all",
    ])
    add_image_slide(prs, "Architecture", "docs/architecture.png")
    add_bullet_slide(prs, "Live Demo", [
        "agents flow through the policy gateway in real time",
        "over-cap action blocked live, exact reason shown inline",
        "fleet-wide EMERGENCY STOP halts every agent instantly",
    ])
    add_bullet_slide(prs, "Business Impact", [
        "prevents a misrouted-agent incident before it reaches a customer",
        "full audit trail for every agent decision, allow or block",
        "operator can reconfigure policy live, no redeploy needed",
    ])
    add_bullet_slide(prs, "Scalability & What's Next", [
        "SQLite -> Postgres, dict-policy engine -> rules service as fleet grows",
        "add per-action-type risk scoring on top of static caps/scopes",
        "pluggable connectors for real agent frameworks",
    ])
    prs.save("deck/CodeStreet_Governance_Deck.pptx")
    print("Saved deck/CodeStreet_Governance_Deck.pptx")


if __name__ == "__main__":
    main()
