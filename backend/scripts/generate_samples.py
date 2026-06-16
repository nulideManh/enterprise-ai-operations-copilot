import os
from docx import Document
from pptx import Presentation

def create_samples():
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../sample_documents"))
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Create hr_policy.docx
    doc1 = Document()
    doc1.add_heading("Enterprise Employee Handbook & HR Policy", 0)
    doc1.add_heading("1. Core Working Hours", 1)
    doc1.add_paragraph(
        "Our core working hours are from 9:00 AM to 5:00 PM, Monday through Friday. "
        "Employees are expected to be available during these hours. Flexible working arrangements "
        "can be discussed with department leads."
    )
    doc1.add_heading("2. Annual Leave and Time Off", 1)
    doc1.add_paragraph(
        "All full-time employees are entitled to 15 days of paid annual leave per calendar year. "
        "Leave requests must be submitted through the HR portal and approved by the department manager "
        "at least 5 business days in advance. Unused leaves up to 5 days can be carried over to the next year."
    )
    doc1.add_heading("3. Health and Wellness Benefits", 1)
    doc1.add_paragraph(
        "We offer comprehensive health, dental, and vision insurance coverage to all full-time employees. "
        "Premium costs are 100% covered by the company for employees, and 50% covered for dependents. "
        "Additionally, employees receive a wellness stipend of $50 per month for gym memberships or wellness activities."
    )
    doc1.save(os.path.join(output_dir, "hr_policy.docx"))
    print("Created hr_policy.docx")

    # 2. Create it_security_guide.pptx
    prs = Presentation()
    
    # Slide 1: Title
    slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(slide_layout)
    title = slide.shapes.title
    subtitle = slide.placeholders[1]
    title.text = "Enterprise IT Security & Remote Work Policy"
    subtitle.text = "Guidelines for Secure Operations"

    # Slide 2: VPN
    slide_layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(slide_layout)
    shapes = slide.shapes
    title_shape = shapes.title
    body_shape = shapes.placeholders[1]
    title_shape.text = "VPN & Remote Connection Rules"
    tf = body_shape.text_frame
    tf.text = "Always use the official Corporate Cisco VPN client when working remotely."
    p2 = tf.add_paragraph()
    p2.text = "Never connect to corporate resources from public Wi-Fi networks (e.g. coffee shops) without VPN enabled."
    p3 = tf.add_paragraph()
    p3.text = "Multi-factor authentication (MFA) via Duo Security is mandatory for all VPN connections."

    # Slide 3: Passwords
    slide = prs.slides.add_slide(slide_layout)
    shapes = slide.shapes
    title_shape = shapes.title
    body_shape = shapes.placeholders[1]
    title_shape.text = "Password Complexity Guidelines"
    tf = body_shape.text_frame
    tf.text = "Passwords must be at least 12 characters in length."
    p2 = tf.add_paragraph()
    p2.text = "Must contain uppercase letters, lowercase letters, numbers, and special symbols (e.g., !, @, #)."
    p3 = tf.add_paragraph()
    p3.text = "Passwords must be rotated every 90 days. Avoid reusing the last 5 passwords."
    
    prs.save(os.path.join(output_dir, "it_security_guide.pptx"))
    print("Created it_security_guide.pptx")

    # 3. Create finance_instructions.docx
    doc2 = Document()
    doc2.add_heading("Corporate Spend & Expense Approvals", 0)
    doc2.add_heading("1. General Expenditure Policies", 1)
    doc2.add_paragraph(
        "All corporate expenses must be business-related, documented with itemized receipts, "
        "and submitted within 30 days of the transaction. Unreceipted transactions above $25 will not be reimbursed."
    )
    doc2.add_heading("2. Approval Limit Matrix", 1)
    p = doc2.add_paragraph()
    p.add_run("The following limits apply to all departmental purchases:\n")
    p.add_run("- Expenses under $500: Department Lead approval required.\n")
    p.add_run("- Expenses from $500 to $5,000: Department Manager approval required.\n")
    p.add_run("- Expenses above $5,000: CFO or Executive Director approval required.\n")
    doc2.add_heading("3. Invoice Submission Flow", 1)
    doc2.add_paragraph(
        "Invoices from vendors must be sent directly to finance-receipts@enterprise.com. "
        "Each invoice must include the Vendor Name, Invoice Number, Amount, Currency, and Issue Date. "
        "Payments are processed on a net-30 schedule after final department sign-off."
    )
    doc2.save(os.path.join(output_dir, "finance_instructions.docx"))
    print("Created finance_instructions.docx")

if __name__ == "__main__":
    create_samples()
