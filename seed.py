"""
Seed script for Tshienda Sneaker Care database.
Populates:
- Owner account (owner@tshienda.co.za / TshiendaOwner2026!)
- Staff account (staff@tshienda.co.za / TshiendaStaff2026!)
- Base pricing & WhatsApp notification templates
- Demo customers with POPIA consent
- Realistic demo orders across all 5 workflow stages with timeline audit logs
"""
import sys, os
from datetime import datetime, timedelta

basedir = os.path.abspath(os.path.dirname(__file__))
if basedir not in sys.path:
    sys.path.insert(0, basedir)

from app import create_app
from app.extensions import db
from app.models import User, Customer, Order, StageLog, Setting
from app.utils.whatsapp import DEFAULT_TEMPLATES

app = create_app('development')

def seed_database():
    with app.app_context():
        print("Initializing database tables...")
        db.create_all()

        owner = User.query.filter_by(email='owner@tshienda.co.za').first()
        if not owner:
            owner = User(name='Rotondwa Ramashia', email='owner@tshienda.co.za', role='owner')
            owner.set_password('TshiendaOwner2026!')
            db.session.add(owner)
            print("Created Owner account: owner@tshienda.co.za (password: TshiendaOwner2026!)")

        staff = User.query.filter_by(email='staff@tshienda.co.za').first()
        if not staff:
            staff = User(name='Thabo Mokoena', email='staff@tshienda.co.za', role='staff')
            staff.set_password('TshiendaStaff2026!')
            db.session.add(staff)
            print("Created Staff account: staff@tshienda.co.za (password: TshiendaStaff2026!)")

        db.session.commit()

        default_settings = {
            'price_standard': '100', 'price_deep': '150', 'price_suede_leather': '200',
            'whatsapp_template_dropped_off': DEFAULT_TEMPLATES['dropped_off'],
            'whatsapp_template_washing': DEFAULT_TEMPLATES['washing'],
            'whatsapp_template_drying': DEFAULT_TEMPLATES['drying'],
            'whatsapp_template_ready': DEFAULT_TEMPLATES['ready'],
            'whatsapp_template_collected': DEFAULT_TEMPLATES['collected']
        }
        for k, v in default_settings.items():
            if not Setting.query.filter_by(key=k).first():
                Setting.set(k, v)
        print("Operational settings & pricing seeded.")

        demo_customers_data = [
            {'name': 'Ayanda Dlamini', 'phone': '27821112233', 'source': 'walk_in'},
            {'name': 'Keanu Petersen', 'phone': '27714445566', 'source': 'instagram'},
            {'name': 'Lwandle Ndlovu', 'phone': '27837778899', 'source': 'friend'},
            {'name': 'Zackaria Adams', 'phone': '27609990011', 'source': 'campus_poster'},
            {'name': 'Naledi Sithole', 'phone': '27845551122', 'source': 'src_event'},
        ]

        customers = []
        for cdata in demo_customers_data:
            c = Customer.query.filter_by(phone=cdata['phone']).first()
            if not c:
                c = Customer(
                    name=cdata['name'], phone=cdata['phone'], consent_flag=True,
                    consent_timestamp=datetime.utcnow() - timedelta(days=5),
                    created_at=datetime.utcnow() - timedelta(days=5)
                )
                db.session.add(c)
                customers.append((c, cdata['source']))
            else:
                customers.append((c, cdata['source']))
        db.session.commit()

        now = datetime.utcnow()
        demo_orders_spec = [
            {
                'code': 'TSH-7K2M9', 'customer_idx': 0, 'service': 'standard', 'pairs': 1, 'price': 100.0,
                'stage': 'dropped_off', 'notes': 'White Nike Air Force 1s. Midsole mud and lace stains.',
                'created_offset': timedelta(hours=2), 'history': [('dropped_off', timedelta(hours=2))]
            },
            {
                'code': 'TSH-4W8B2', 'customer_idx': 1, 'service': 'deep', 'pairs': 1, 'price': 150.0,
                'stage': 'washing', 'notes': 'Adidas Sambas. Muddy sole scrub and deodorizing requested.',
                'created_offset': timedelta(hours=6),
                'history': [('dropped_off', timedelta(hours=6)), ('washing', timedelta(hours=1))]
            },
            {
                'code': 'TSH-9R1P6', 'customer_idx': 2, 'service': 'suede_leather', 'pairs': 2, 'price': 400.0,
                'stage': 'drying', 'notes': 'Pair 1: Jordan 4 Grey Suede nap restore. Pair 2: New Balance 550 leather hydration.',
                'created_offset': timedelta(days=1, hours=3),
                'history': [('dropped_off', timedelta(days=1, hours=3)), ('washing', timedelta(hours=18)), ('drying', timedelta(hours=4))]
            },
            {
                'code': 'TSH-2M5T8', 'customer_idx': 3, 'service': 'standard', 'pairs': 1, 'price': 100.0,
                'stage': 'ready', 'notes': 'Converse Chuck 70 High black. Full canvas freshen-up.',
                'created_offset': timedelta(days=1, hours=8),
                'history': [('dropped_off', timedelta(days=1, hours=8)), ('washing', timedelta(days=1)), ('drying', timedelta(hours=14)), ('ready', timedelta(hours=2))]
            },
            {
                'code': 'TSH-6H3X7', 'customer_idx': 4, 'service': 'deep', 'pairs': 2, 'price': 300.0,
                'stage': 'collected', 'notes': 'Puma Suede navy & Vans Old Skool. Collected by customer.',
                'created_offset': timedelta(days=3),
                'history': [('dropped_off', timedelta(days=3)), ('washing', timedelta(days=2, hours=18)), ('drying', timedelta(days=2, hours=6)), ('ready', timedelta(days=1, hours=12)), ('collected', timedelta(hours=8))]
            }
        ]

        for spec in demo_orders_spec:
            existing = Order.query.filter_by(order_number=spec['code']).first()
            if not existing:
                cust, ref_src = customers[spec['customer_idx']]
                ord_created = now - spec['created_offset']
                ord_obj = Order(
                    order_number=spec['code'], customer_id=cust.id, service=spec['service'],
                    pairs=spec['pairs'], price=spec['price'], stage=spec['stage'],
                    notes=spec['notes'], source=ref_src, created_at=ord_created,
                    updated_at=now - spec['history'][-1][1]
                )
                db.session.add(ord_obj)
                db.session.commit()
                for stg, offset in spec['history']:
                    log = StageLog(
                        order_id=ord_obj.id, stage=stg, user_id=staff.id,
                        timestamp=now - offset, notes=f"Stage progression: {stg.replace('_', ' ').title()}"
                    )
                    db.session.add(log)
                db.session.commit()
                print(f"Created demo order {spec['code']} ({spec['stage']}) for {cust.name}")

        print()
        print("Seed completed successfully!")
        print("--------------------------------------------------")
        print("Owner Login: owner@tshienda.co.za / TshiendaOwner2026!")
        print("Staff Login: staff@tshienda.co.za / TshiendaStaff2026!")
        print("Demo Order Numbers: TSH-7K2M9, TSH-4W8B2, TSH-9R1P6, TSH-2M5T8, TSH-6H3X7")
        print("--------------------------------------------------")

if __name__ == '__main__':
    seed_database()
