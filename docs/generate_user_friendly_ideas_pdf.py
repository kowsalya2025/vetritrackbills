from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


BASE_DIR = Path(__file__).resolve().parent
OUTPUT = BASE_DIR / "vetripintrack_user_friendly_ideas.pdf"


def para(text, style):
    return Paragraph(text, style)


def bullets(items, style):
    return ListFlowable(
        [ListItem(Paragraph(item, style), leftIndent=12) for item in items],
        bulletType="bullet",
        leftIndent=16,
    )


def table_rows(rows, header_style, body_style):
    output = []
    for index, row in enumerate(rows):
        style = header_style if index == 0 else body_style
        output.append([Paragraph(str(cell), style) for cell in row])
    return output


def build_pdf():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CoverTitle",
            parent=styles["Title"],
            fontSize=22,
            leading=28,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#123047"),
            spaceAfter=14,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverSub",
            parent=styles["BodyText"],
            fontSize=11,
            leading=16,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#4B5563"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading1"],
            fontSize=15,
            leading=19,
            textColor=colors.HexColor("#123047"),
            spaceBefore=12,
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["BodyText"],
            fontSize=9.3,
            leading=13,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableHeader",
            parent=styles["BodyText"],
            fontSize=8.2,
            leading=10,
            textColor=colors.white,
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableCell",
            parent=styles["BodyText"],
            fontSize=7.8,
            leading=9.8,
            textColor=colors.HexColor("#111827"),
        )
    )

    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title="Vetri PinTrack User-Friendly Improvement Ideas",
        author="Vetri PinTrack Project Team",
    )

    story = [
        para("Vetri PinTrack", styles["CoverTitle"]),
        para("User-Friendly Improvement Ideas", styles["CoverSub"]),
        para("Prepared for product and project discussion", styles["CoverSub"]),
        para("Date: 02 May 2026", styles["CoverSub"]),
        Spacer(1, 0.25 * inch),
    ]

    story.append(para("1. Goal", styles["SectionTitle"]))
    story.append(
        para(
            "The goal is to make Vetri PinTrack simple for daily users: clear dashboard, fast bill payment, useful reminders, safe payment communication, and easy financial tracking.",
            styles["Body"],
        )
    )

    story.append(para("2. Best User-Friendly Options", styles["SectionTitle"]))
    data = [
        ["Feature Area", "Improvement Idea", "Why It Helps Users"],
        ["Onboarding", "Show progress like Step 2 of 6, autosave each step, and allow Skip/Continue Later.", "Reduces confusion and prevents users from losing data."],
        ["Dashboard", "Add quick action buttons: Add Bill, Add Expense, Add Income, Pay Bill.", "Users can complete important tasks faster."],
        ["Bills", "Show bills by status: Due Today, Due Soon, Overdue, Paid, Failed.", "Users immediately know what needs attention."],
        ["Payments", "Show a payment timeline: Created, Redirected, Pending, Success, Failed.", "Users feel confident during PhonePe payment flow."],
        ["Reminders", "Allow reminders by email, SMS, WhatsApp, or in-app notification.", "Users can choose the channel they actually check."],
        ["Budgets", "Show progress bars for each budget with 50%, 80%, and 100% alerts.", "Users can control spending before crossing limits."],
        ["Reports", "Add monthly PDF and CSV reports for bills, expenses, income, and payments.", "Users can share reports or keep records."],
        ["Receipts", "Create a receipt center with paid bill receipts and download option.", "Users can easily find payment proof."],
        ["Support", "Add payment issue reporting with support ticket/reference number.", "Users know what to do when payment fails or stays pending."],
        ["Accessibility", "Use readable font sizes, strong contrast, clear error messages, and mobile-first forms.", "More users can use the product comfortably."],
    ]
    table = Table(
        table_rows(data, styles["TableHeader"], styles["TableCell"]),
        colWidths=[1.25 * inch, 3.05 * inch, 2.2 * inch],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123047")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(table)

    story.append(para("3. High-Impact Ideas for First Release", styles["SectionTitle"]))
    story.append(
        bullets(
            [
                "<b>Smart empty states:</b> If there are no bills, show Add Your First Bill instead of a blank area.",
                "<b>Payment safety message:</b> Before redirecting to PhonePe, clearly say that Vetri PinTrack will never ask for UPI PIN, OTP, CVV, or card PIN.",
                "<b>Retry payment:</b> If a payment fails, show Retry Payment and Contact Support options.",
                "<b>Due reminder preferences:</b> Let users choose reminders 7 days before, 3 days before, due date, and overdue.",
                "<b>Monthly insight cards:</b> Show simple messages such as You saved 18% this month or Bills increased by Rs. 500.",
                "<b>Mobile-friendly Pay Now:</b> Keep bill details, amount, and Pay Now button visible and easy to tap on mobile.",
                "<b>Receipt download:</b> After successful payment, provide Download Receipt and Back to Dashboard buttons.",
                "<b>Trust section:</b> Explain what data is stored, what is masked, and what is never stored.",
            ],
            styles["Body"],
        )
    )

    story.append(para("4. Recommended Implementation Order", styles["SectionTitle"]))
    story.append(
        bullets(
            [
                "First: quick actions, empty states, clean bill statuses, and payment timeline.",
                "Second: reminder preferences, receipt center, and budget progress bars.",
                "Third: monthly reports, spending insights, support tickets, and advanced notifications.",
            ],
            styles["Body"],
        )
    )

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#6B7280"))
        canvas.drawString(0.65 * inch, 0.35 * inch, "Vetri PinTrack User-Friendly Ideas")
        canvas.drawRightString(7.6 * inch, 0.35 * inch, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    build_pdf()
    print(OUTPUT)
