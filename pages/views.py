# ...existing code...
from django.utils.text import slugify
# ...existing code...
# Create your views here.
from django.shortcuts import render, redirect
from .models import GigCreation
from .firebase_utils import FirestoreClient
firebase_client = FirestoreClient()

def index(request):
    jobs = firebase_client.query_collection('app_jobs', filters=[{'field': 'is_avail', 'operator': 'EQUAL', 'value': True}])
    return render(request, 'pages/index.html', {'jobs': jobs})

def gig_creation(request):
    if request.method == 'POST':
        data = request.POST
        offers = data.get('offers', '')
        offers_list = [o.strip() for o in offers.split(',')] if offers else []
        gig = GigCreation.objects.create(
            title=data.get('title', ''),
            full_name=data.get('full_name', ''),
            phone_number=data.get('phone', ''),
            email=data.get('email', ''),
            deadline=data.get('deadline'),
            time=data.get('time'),
            min_price=data.get('price_min') or None,
            max_price=data.get('price_max') or None,
            description=data.get('description', ''),
            gig_category=data.get('category', ''),
            gig_review=data.get('gig_review', ''),
            gig_comment=data.get('gig_comment', ''),
            gig_kreyate_id=data.get('gig_kreyate_id') or None,
            gig_kreyate_name=data.get('gig_kreyate_name', ''),
            gig_kreyate_review=data.get('gig_kreyate_review', ''),
            gig_city=data.get('gig_city', ''),
            gig_state=data.get('gig_state', ''),
            gig_country=data.get('gig_country', ''),
            kreyate_city=data.get('kreyate_city', ''),
            kreyate_state=data.get('kreyate_state', ''),
            kreyate_country=data.get('kreyate_country', ''),
            kreyate_fee=data.get('kreyate_fee') or None,
            gig_kreyate_fee=data.get('gig_kreyate_fee') or None,
            amount_paid=data.get('amount_paid') or None,
            currency=data.get('currency', ''),
            method_payment=data.get('method_payment', ''),
            kreyate_phone=data.get('kreyate_phone', ''),
            offers=offers_list,
        )

        # Prepare Firebase data from GigCreation instance
        firebase_data = {
            "bizID": "",
            "bizName": gig.full_name,
            "city": gig.gig_city,
            "content": gig.description,
            "created_on": gig.posted_at.isoformat() if gig.posted_at else None,
            "end_time": gig.deadline.strftime('%Y-%m-%dT00:00:00') if hasattr(gig.deadline, 'strftime') else str(gig.deadline) if gig.deadline else None,
            "has_link": False,
            "id": gig.id,
            "is_avail": True,
            "is_paid": True,
            "jobSlug": slugify(gig.title) if gig.title else "",
            "job_link": "",
            "posImg": "_posImg",
            "pos_cos": 0,
            "pos_duration": "as long as",
            "position": gig.gig_category,
            "post_by": gig.full_name,
            "salary": f"${float(gig.min_price):.2f} - ${float(gig.max_price):.2f}" if gig.min_price and gig.max_price else f"${float(gig.min_price):.2f}" if gig.min_price else "",
            "state": gig.gig_state,
            "title": gig.title,
            "zip": data.get('zip', ''),
            "job_category": {
                "app": False,
                "banmgig": False,
            },
            "gig_creation": {
                "title": gig.title,
                "full_name": gig.full_name,
                "phone_number": gig.phone_number,
                "email": gig.email,
                "deadline": gig.deadline.strftime('%Y-%m-%d') if hasattr(gig.deadline, 'strftime') else str(gig.deadline) if gig.deadline else None,
                "time": gig.time.isoformat() if gig.time else None,
                "min_price": gig.min_price,
                "max_price": gig.max_price,
                "description": gig.description,
                "gig_category": gig.gig_category,
                "gig_review": gig.gig_review,
                "gig_comment": gig.gig_comment,
                "gig_kreyate_id": gig.gig_kreyate_id,
                "gig_kreyate_name": gig.gig_kreyate_name,
                "gig_kreyate_review": gig.gig_kreyate_review,
                "gig_city": gig.gig_city,
                "gig_state": gig.gig_state,
                "gig_country": gig.gig_country,
                "kreyate_city": gig.kreyate_city,
                "kreyate_state": gig.kreyate_state,
                "kreyate_country": gig.kreyate_country,
                "kreyate_fee": gig.kreyate_fee,
                "gig_kreyate_fee": gig.gig_kreyate_fee,
                "amount_paid": gig.amount_paid,
                "currency": gig.currency,
                "method_payment": gig.method_payment,
                "kreyate_phone": gig.kreyate_phone,
            }
        }

        # Save to Firebase using FirestoreClient
        result = firebase_client.set_document('app_jobs', firebase_data['id'], firebase_data)
        if not result:
            print('Firebase document creation failed for:', firebase_data['id'])
        else:
            print('Firebase document created successfully:', firebase_data['id'])

        return redirect('pages:index')
    return render(request, 'pages/gig_creation.html')