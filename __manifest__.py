{
    'name': 'NexTechis Website Booking System',
    'version': '19.0.3.0.0',
    'category': 'Website/Website',
    'summary': 'Bookable products with plans, time slots, capacity limits and website checkout',
    'description': """
Website booking system
======================
* Mark any product as a *Booking Product*
* Global Plans (Silver / Gold ...) and Time Slots (09:00 - 11:00 ...)
* Per product: booking period, advance limit, closing periods, open weekdays (others are shown as Closed),
  plan prices and max booking quantity
* "Book Now" popup on the product page: pick a date, a time slot, a plan and the guests,
  then checkout
* Booking Orders are generated automatically when the sale order is confirmed
""",
    'author': 'NexTechis Software Solutions',
    'website': 'https://nextechis.in',
    'license': 'OPL-1',
    'images': ['static/description/banner.png'],
    'depends': ['website_sale', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/booking_security.xml',
        'data/booking_data.xml',
        'views/booking_plan_views.xml',
        'views/booking_time_slot_views.xml',
        'views/booking_closing_period_views.xml',
        'views/booking_order_views.xml',
        'views/product_views.xml',
        'views/booking_templates.xml',
        'views/booking_menus.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'nextechis_website_booking_system/static/src/css/booking_wizard.css',
            'nextechis_website_booking_system/static/src/js/booking_wizard.js',
        ],
    },
    'application': True,
    'installable': True,
    'price': 15,
    'currency': 'USD',
}