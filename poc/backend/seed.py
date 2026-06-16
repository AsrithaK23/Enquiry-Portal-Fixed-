import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from database import db
from models import Enquiry, ActivityLog, Client
from services.ai_service import analyse
from datetime import datetime, timedelta

SAMPLES = [
    {"customer_name":"Rahul Sharma",   "phone":"9876543210","email":"rahul@techcorp.in",    "source":"Website",   "follow_up_date":"2026-05-20","description":"We need a full e-commerce website with payment gateway, product catalog and admin panel. We want it done within 2 months."},
    {"customer_name":"Priya Nair",     "phone":"9123456789","email":"priya@bloom.com",       "source":"Referral",  "follow_up_date":"2026-05-18","description":"Looking for a mobile app for our interior design portfolio and client booking system. Need iOS and Android both."},
    {"customer_name":"Arjun Mehta",    "phone":"9988776655","email":"arjun@retailmax.com",   "source":"Phone Call","follow_up_date":"2026-05-15","description":"We need an ERP system with inventory management, billing module, purchase orders and payroll. Urgent requirement."},
    {"customer_name":"Sneha Kulkarni", "phone":"8765432109","email":"sneha@edulearn.in",     "source":"Email",     "follow_up_date":"2026-05-25","description":"We want a web app portal for online courses with video streaming, quiz module and student progress tracking system."},
    {"customer_name":"Vikas Patel",    "phone":"9871234567","email":"vikas@healthfirst.com", "source":"WhatsApp",  "follow_up_date":"","description":"Our website is completely down. Need urgent support and a monthly maintenance contract. This is very critical for our business."},
    {"customer_name":"Divya Reddy",    "phone":"9012345678","email":"divya@startup.in",      "source":"Website",   "follow_up_date":"2026-05-30","description":"Simple landing page with lead capture form and email automation integration. We have a low budget but need it soon."},
    {"customer_name":"Kiran Rao",      "phone":"9345678901","email":"kiran@automart.in",     "source":"Referral",  "follow_up_date":"2026-05-19","description":"We need a CRM system for managing car leads, follow-ups, test drive bookings and our sales pipeline tracking."},
    {"customer_name":"Meena Joshi",    "phone":"9456789012","email":"meena@foodbox.in",      "source":"Website",   "follow_up_date":"2026-05-22","description":"Food delivery mobile app with real-time order tracking, payment integration, customer app and restaurant dashboard."},
    {"customer_name":"Suresh Kumar",   "phone":"9567890123","email":"suresh@buildright.com", "source":"Walk-in",   "follow_up_date":"2026-05-17","description":"Company portfolio website with project showcase, team page and contact form. We need it within 3 weeks for a tender."},
    {"customer_name":"Ananya Singh",   "phone":"9678901234","email":"ananya@logitrack.in",   "source":"Email",     "follow_up_date":"2026-05-28","description":"Logistics platform for tracking shipments, managing fleet, driver app and generating daily delivery reports."},
    {"customer_name":"Ravi Shankar",   "phone":"9789012345","email":"ravi@cloudsoft.io",     "source":"Referral",  "follow_up_date":"","description":"Production server is down immediately. Need emergency DevOps support and deployment fix. This is a critical issue for us."},
    {"customer_name":"Pooja Verma",    "phone":"9890123456","email":"pooja@fashionhub.in",   "source":"WhatsApp",  "follow_up_date":"2026-05-21","description":"E-commerce website for our fashion brand with wishlist, size guide, Instagram feed integration and gift card feature."},
    {"customer_name":"Nikhil Garg",    "phone":"9901234567","email":"nikhil@edukids.com",    "source":"Website",   "follow_up_date":"2026-05-16","description":"Interactive web application for kids with animated lessons, parent dashboard and learning progress tracker."},
    {"customer_name":"Kavya Iyer",     "phone":"9012345670","email":"kavya@fintrack.in",     "source":"Referral",  "follow_up_date":"2026-05-30","description":"Accounting software with GST billing, income and expense tracker and financial reporting for small business owners."},
    {"customer_name":"Sanjay Desai",   "phone":"9123456701","email":"sanjay@mediapros.in",   "source":"Email",     "follow_up_date":"2026-05-24","description":"Corporate website redesign with modern UI, animations and a blog section. New company branding needs to be applied."},
    {"customer_name":"Lakshmi Pillai", "phone":"9234567012","email":"lakshmi@hospitease.com","source":"Phone Call","follow_up_date":"2026-05-20","description":"Hospital management system with patient records, appointment booking, billing and doctor scheduling platform."},
    {"customer_name":"Vikram Nair",    "phone":"9345670123","email":"vikram@realnest.in",    "source":"Website",   "follow_up_date":"2026-06-01","description":"Real estate website with property listings, map view, EMI calculator and agent login portal for managing listings."},
    {"customer_name":"Deepa Krishnan", "phone":"9456701234","email":"deepa@printworld.in",   "source":"WhatsApp",  "follow_up_date":"","description":"Online print portal where customers upload their designs, choose products and track their print and delivery orders."},
    {"customer_name":"Arun Bhat",      "phone":"9567012345","email":"arun@safeguard.in",     "source":"Referral",  "follow_up_date":"2026-05-23","description":"Web dashboard for monitoring CCTV cameras and managing security guard attendance across multiple city branches."},
    {"customer_name":"Sunita Rao",     "phone":"9670123456","email":"sunita@greenfarm.in",   "source":"Website",   "follow_up_date":"2026-06-05","description":"Farmer marketplace platform to connect buyers directly with farmers. Needs multilingual support and a mobile application."},
]

STATUS_MAP = [
    "New","In Discussion","Quoted","Closed","Dropped",
    "New","In Discussion","New","Quoted","New",
    "Closed","In Discussion","Quoted","New","New",
    "In Discussion","New","Dropped","Quoted","New",
]

def seed():
    app = create_app()
    with app.app_context():
        if Enquiry.query.count() >= 20:
            print("⚠️  Already seeded. Skipping.")
            return
        for i, s in enumerate(SAMPLES):
            ai = analyse(s["description"])

            # create matching client record too
            client = Client.query.filter_by(email=s["email"]).first()
            if not client:
                client = Client(name=s["customer_name"], email=s["email"],
                                 phone=s["phone"], company="")
                db.session.add(client)
                db.session.flush()

            enq = Enquiry(
                client_id      = client.id,
                customer_name  = s["customer_name"],
                phone          = s["phone"],
                email          = s["email"],
                source         = s["source"],
                description    = s["description"],
                category       = ai["category"],
                priority       = ai["priority"],
                ai_summary     = ai["ai_summary"],
                status         = STATUS_MAP[i],
                follow_up_date = s["follow_up_date"],
                notes          = "",
                created_at     = datetime.utcnow() - timedelta(days=20 - i),
            )
            db.session.add(enq)
            db.session.flush()
            db.session.add(ActivityLog(
                enquiry_id=enq.id,
                action=f"Enquiry created. Category: {enq.category}, Priority: {enq.priority}"
            ))
        db.session.commit()
        print(f"✅ Seeded {len(SAMPLES)} enquiries and matching clients.")

if __name__ == "__main__":
    seed()
